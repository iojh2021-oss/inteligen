"""Durable SQLite memory with provenance and deterministic lexical retrieval.

Retrieval is intentionally dependency-free and works with Unicode word tokens,
including Persian. It is not semantic/vector search; it ranks matching memories
using a BM25-style score over both the original prompt and saved answer.
"""
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config


def _db():
    path = Path(config.database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        world TEXT NOT NULL,
        prompt TEXT NOT NULL,
        result TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    # Migration: older databases lack request_id.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(memories)")}
    if "request_id" not in cols:
        conn.execute("ALTER TABLE memories ADD COLUMN request_id TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS world_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        world TEXT NOT NULL,
        request_id TEXT,
        ok INTEGER NOT NULL,
        latency_ms INTEGER NOT NULL,
        output_chars INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(world: str, prompt: str, result: str, request_id: str = None):
    conn = _db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO memories(world,prompt,result,created_at,request_id) VALUES(?,?,?,?,?)",
                (world, prompt[:8000], result[:12000], _now(), request_id),
            )
    finally:
        conn.close()


def _rows(sql: str, params=()):
    conn = _db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _item(r) -> dict:
    return {"id": r[0], "world": r[1], "prompt": r[2], "result": r[3],
            "created_at": r[4], "request_id": r[5]}


_COLS = "id,world,prompt,result,created_at,request_id"


def recent(limit: int = 20):
    rows = _rows(f"SELECT {_COLS} FROM memories ORDER BY id DESC LIMIT ?",
                 (min(max(limit, 1), 100),))
    return [_item(r) for r in rows]


def _tokens(text: str) -> list[str]:
    """Unicode-aware tokens; retain a list so term frequency is measurable."""
    return [t for t in re.findall(r"\w+", (text or "").casefold()) if len(t) >= 2]


def relevant(world: str, question: str, limit: int = 3):
    """Rank this world's memories by BM25-style lexical relevance.

    Both the original prompt and saved answer are searchable. Prompt matches
    receive extra weight, exact phrase matches receive a small boost, and
    recency breaks equal-score ties. No external model or network is used.
    """
    query_tokens = _tokens(question)
    if not query_tokens:
        return []
    safe_limit = min(max(int(limit), 1), 20)
    rows = _rows(
        f"SELECT {_COLS} FROM memories WHERE world=? ORDER BY id DESC LIMIT 500",
        (world,),
    )
    if not rows:
        return []

    documents = []
    document_frequency = {}
    for row in rows:
        prompt_tokens = _tokens(row[2])
        result_tokens = _tokens(row[3])
        # Prompt weight is 2x; answers remain searchable at normal weight.
        weighted_tokens = prompt_tokens + prompt_tokens + result_tokens
        frequencies = {}
        for token in weighted_tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
        documents.append((row, frequencies, len(weighted_tokens)))
        for token in set(weighted_tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    average_length = sum(doc[2] for doc in documents) / max(len(documents), 1)
    query_frequency = {}
    for token in query_tokens:
        query_frequency[token] = query_frequency.get(token, 0) + 1

    ranked = []
    k1, b = 1.2, 0.75
    for row, frequencies, doc_length in documents:
        score = 0.0
        for token, qf in query_frequency.items():
            tf = frequencies.get(token, 0)
            if not tf:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * doc_length / max(average_length, 1))
            score += idf * (tf * (k1 + 1) / denominator) * (1 + math.log(qf))

        prompt_text = " ".join(_tokens(row[2]))
        query_phrase = " ".join(query_tokens)
        if len(query_tokens) > 1 and query_phrase in prompt_text:
            score += 1.0
        if score > 0:
            ranked.append((score, row[0], row))

    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [_item(entry[2]) for entry in ranked[:safe_limit]]


def forget(memory_id: int) -> bool:
    conn = _db()
    try:
        with conn:
            cur = conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        return cur.rowcount > 0
    finally:
        conn.close()


def record_metric(world: str, request_id: str, ok: bool, latency_ms: int, output_chars: int):
    conn = _db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO world_metrics(world,request_id,ok,latency_ms,output_chars,created_at) VALUES(?,?,?,?,?,?)",
                (world, request_id, 1 if ok else 0, latency_ms, output_chars, _now()),
            )
    finally:
        conn.close()


def metrics_summary() -> dict:
    rows = _rows("""SELECT world, COUNT(*), SUM(ok), AVG(latency_ms), AVG(CASE WHEN ok=1 THEN output_chars END)
                    FROM world_metrics GROUP BY world""")
    return {
        r[0]: {
            "runs": r[1],
            "success_rate": round((r[2] or 0) / r[1], 3),
            "avg_latency_ms": int(r[3] or 0),
            "avg_output_chars": int(r[4] or 0),
        }
        for r in rows
    }
