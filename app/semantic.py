"""Optional local multilingual dense embeddings for hybrid memory retrieval.

The model runs on the current machine/Actions runner; no embedding API is used.
When unavailable or disabled, callers keep the deterministic BM25 fallback.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Iterable

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION = "multilingual-minilm-l12-v2"
DIMENSION = 384
_model = None


class SemanticUnavailable(RuntimeError):
    pass


def enabled() -> bool:
    return os.getenv("INTELIGEN_SEMANTIC_MEMORY", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def model_loaded() -> bool:
    return _model is not None


def _get_model():
    global _model
    if _model is not None:
        return _model
    if not enabled():
        raise SemanticUnavailable("Semantic memory is disabled")
    try:
        from fastembed import TextEmbedding
        cache_dir = Path(os.getenv(
            "FASTEMBED_CACHE_PATH", str(Path.home() / ".cache" / "fastembed")
        )).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache_dir))
        return _model
    except Exception as exc:
        raise SemanticUnavailable(f"Local embedding model unavailable: {exc}") from exc


def embed_text(text: str) -> list[float]:
    """Create one normalized local embedding; reject empty or malformed vectors."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding text must not be empty")
    try:
        vectors = list(_get_model().embed([text[:8000]]))
        vector = [float(value) for value in vectors[0]]
    except SemanticUnavailable:
        raise
    except Exception as exc:
        raise SemanticUnavailable(f"Embedding inference failed: {exc}") from exc
    if len(vector) != DIMENSION or not all(math.isfinite(v) for v in vector):
        raise SemanticUnavailable("Embedding model returned an invalid vector")
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        raise SemanticUnavailable("Embedding model returned a zero vector")
    return [value / norm for value in vector]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = list(left), list(right)
    if len(a) != len(b) or not a:
        raise ValueError("Vectors must have the same non-zero dimension")
    return sum(x * y for x, y in zip(a, b))


def rank_documents(query_vector: list[float], documents: list[tuple[int, list[float]]]) -> list[tuple[int, float]]:
    """Return (document id, cosine score), highest first."""
    ranked = [
        (int(doc_id), cosine_similarity(query_vector, vector))
        for doc_id, vector in documents
    ]
    ranked.sort(key=lambda item: (item[1], item[0]), reverse=True)
    return ranked
