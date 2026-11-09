"""Deterministic, dependency-free lexical retrieval for world-scoped memory.

This is a BM25-style ranker, not semantic/vector search. It keeps retrieval
explainable and reproducible while the project remains runnable on GitHub CI.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Sequence

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tokenize Unicode text (including Persian); discard one-character noise."""
    normalized = (text or "").casefold().replace("\u200c", "")
    return [token for token in _TOKEN_RE.findall(normalized) if len(token) >= 2]


def rank_rows(rows: Iterable[Sequence], query: str, limit: int = 3) -> list[Sequence]:
    """Rank SQLite memory rows by BM25-style relevance, phrase match, then recency.

    Row layout is the memory table projection: id, world, prompt, result,
    created_at, request_id. Only prompt text is indexed to avoid matching an
    answer merely because it repeats common query terms.
    """
    if limit <= 0:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    documents = []
    for row in rows:
        tokens = tokenize(row[2])
        if tokens:
            documents.append((row, tokens, Counter(tokens)))
    if not documents:
        return []

    doc_count = len(documents)
    avg_length = sum(len(tokens) for _, tokens, _ in documents) / doc_count
    query_terms = set(query_tokens)
    document_frequency = {
        term: sum(1 for _, _, counts in documents if counts.get(term, 0))
        for term in query_terms
    }
    normalized_query = " ".join(query_tokens)

    scored = []
    k1, b = 1.5, 0.75
    for row, tokens, counts in documents:
        length = len(tokens)
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            idf = math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1.0 - b + b * length / max(avg_length, 1.0))
            score += idf * (frequency * (k1 + 1.0)) / denominator

        if score <= 0:
            continue
        prompt_tokens = " ".join(tokens)
        if normalized_query and normalized_query in prompt_tokens:
            score += 1.0
        # IDs are monotonically increasing; recency only breaks relevance ties.
        scored.append((score, row[0], row))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:limit]]
