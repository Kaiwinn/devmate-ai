# rag/embedder.py
"""
Embedder — convert text thành vector số.

Tại sao sentence-transformers thay vì Anthropic embedding API?
- Free, chạy local, không tốn token
- all-MiniLM-L6-v2: 384 dimensions, nhanh, chất lượng tốt cho code search
- Lần đầu chạy sẽ download model ~90MB, sau đó cache local

Embedding là gì (giải thích nhanh):
- Text → vector 384 số (vd: [0.12, -0.34, 0.89, ...])
- Văn bản có nghĩa giống nhau → vectors "gần nhau" trong không gian 384 chiều
- "cosine similarity" đo góc giữa 2 vectors → similarity score 0-1
"""

from sentence_transformers import SentenceTransformer

# Singleton model — load 1 lần, dùng nhiều lần
_model: SentenceTransformer | None = None
MODEL_NAME = "all-MiniLM-L6-v2"


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convert list of texts → list of embedding vectors.
    Batch processing để tối ưu tốc độ.
    """
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Embed 1 text — dùng cho query."""
    return embed_texts([text])[0]
