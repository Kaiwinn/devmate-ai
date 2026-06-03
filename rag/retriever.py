# rag/retriever.py
"""
Hybrid Retriever — kết hợp Semantic Search + BM25 + Cross-Encoder Rerank.

Tại sao 3 lớp?

1. SEMANTIC SEARCH (ChromaDB):
   - Tìm theo ý nghĩa: "lỗi khi gọi API" → match "exception handling"
   - Nhược điểm: miss từ khoá chính xác

2. BM25 (keyword):
   - Tìm theo từ khoá: "exponential backoff" → match chính xác tên function
   - Nhược điểm: miss synonym, không hiểu ngữ nghĩa

3. CROSS-ENCODER RERANK:
   - Score lại top kết quả bằng model nhỏ
   - Cross-encoder đọc CÙNG LÚC query + chunk → score relevance chính xác hơn
   - Bi-encoder (embedding thông thường) đọc query và chunk RIÊNG LẼ → kém hơn

Kết hợp: RRF (Reciprocal Rank Fusion) merge 2 list →
         Cross-encoder rerank top-20 → trả về top-5.
"""

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from rag.chunker import Chunk
from rag.embedder import embed_single
from rag.store import semantic_search

# Cross-encoder nhỏ, chạy local, ~80MB
_cross_encoder: CrossEncoder | None = None
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
    return _cross_encoder


def bm25_search(query: str, chunks: list[Chunk], top_k: int = 20) -> list[dict]:
    """
    BM25 keyword search trên toàn bộ chunks.
    BM25Okapi = cải tiến của TF-IDF, chuẩn của Elasticsearch/Lucene.
    """
    if not chunks:
        return []

    # Tokenize: lowercase + split by whitespace/punctuation
    tokenized_corpus = [c.content.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)

    # Sort theo score, lấy top_k
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for idx in ranked_indices:
        if scores[idx] > 0:  # Bỏ qua chunk không có match nào
            results.append({
                "content": chunks[idx].content,
                "metadata": {
                    "source_file": chunks[idx].source_file,
                    "chunk_type": chunks[idx].chunk_type,
                    "name": chunks[idx].name,
                    "start_line": chunks[idx].start_line,
                    "end_line": chunks[idx].end_line,
                },
                "score": float(scores[idx]),
                "rank": ranked_indices.index(idx) + 1,
            })

    return results


def rrf_merge(
    semantic_hits: list[dict],
    bm25_hits: list[dict],
    k: int = 60,
) -> list[dict]:
    """
    Reciprocal Rank Fusion — merge 2 ranked lists thành 1.

    Công thức: score(doc) = Σ 1/(k + rank_i)
    k=60 là default từ paper gốc (Cormack 2009).

    Lý do dùng RRF thay vì weighted sum:
    - Không cần tune weights (semantic vs BM25 có score scale khác nhau)
    - Robust: document xuất hiện trong nhiều lists → score cao
    """
    scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for rank, hit in enumerate(semantic_hits, 1):
        doc_id = hit["metadata"].get("source_file", "") + hit["content"][:50]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
        content_map[doc_id] = hit

    for rank, hit in enumerate(bm25_hits, 1):
        doc_id = hit["metadata"].get("source_file", "") + hit["content"][:50]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
        content_map[doc_id] = hit

    # Sort theo RRF score
    sorted_ids = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)

    merged = []
    for doc_id in sorted_ids:
        hit = content_map[doc_id].copy()
        hit["rrf_score"] = scores[doc_id]
        merged.append(hit)

    return merged


def rerank(query: str, hits: list[dict], top_k: int = 5) -> list[dict]:
    """
    Cross-encoder rerank: score lại top candidates.

    Khác biệt với embedding (bi-encoder):
    - Bi-encoder: embed(query) + embed(doc) → cosine → fast nhưng less accurate
    - Cross-encoder: encode(query + doc together) → score → slow nhưng accurate
    → Dùng bi-encoder để filter top-20, cross-encoder để rerank top-5
    """
    if not hits:
        return []

    encoder = get_cross_encoder()
    pairs = [(query, h["content"]) for h in hits]
    scores = encoder.predict(pairs)

    # Attach score và sort
    for hit, score in zip(hits, scores):
        hit["rerank_score"] = float(score)

    reranked = sorted(hits, key=lambda h: h["rerank_score"], reverse=True)
    return reranked[:top_k]


def hybrid_retrieve(
    query: str,
    all_chunks: list[Chunk],
    top_k_final: int = 5,
    top_k_candidates: int = 20,
) -> list[dict]:
    """
    Full hybrid retrieval pipeline:
    semantic(top-20) + BM25(top-20) → RRF merge → cross-encoder rerank → top-5
    """
    # 1. Semantic search qua ChromaDB
    query_embedding = embed_single(query)
    semantic_hits = semantic_search(query_embedding, top_k=top_k_candidates)

    # 2. BM25 keyword search
    bm25_hits = bm25_search(query, all_chunks, top_k=top_k_candidates)

    # 3. RRF merge
    merged = rrf_merge(semantic_hits, bm25_hits)[:top_k_candidates]

    # 4. Cross-encoder rerank
    final = rerank(query, merged, top_k=top_k_final)

    return final
