"""Durable SQLite memory with provenance (request_id, world, timestamp), per-world
retrieval, forgetting, and per-world capability metrics."""
import math
import re
import sqlite3
from collections import Counter
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
    # Migration: memory kinds (experience, experiment, decision, failure ...).
    if "kind" not in cols:
        conn.execute("ALTER TABLE memories ADD COLUMN kind TEXT DEFAULT 'experience'")
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


KINDS = ("experience", "experiment", "decision", "failure")


def save(world: str, prompt: str, result: str, request_id: str = None, kind: str = "experience"):
    if kind not in KINDS:
        raise ValueError(f"Unknown memory kind: {kind}")
    conn = _db()
    try:
        with conn:
            # No duplicate records: identical world, kind, prompt and result are stored once.
            same = conn.execute(
                "SELECT 1 FROM memories WHERE world=? AND kind=? AND prompt=? AND result=? LIMIT 1",
                (world, kind, prompt[:8000], result[:12000])).fetchone()
            if same:
                return
            conn.execute(
                "INSERT INTO memories(world,prompt,result,created_at,request_id,kind) VALUES(?,?,?,?,?,?)",
                (world, prompt[:8000], result[:12000], _now(), request_id, kind),
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
            "created_at": r[4], "request_id": r[5], "kind": r[6] or "experience"}


_COLS = "id,world,prompt,result,created_at,request_id,kind"


def recent(limit: int = 20):
    rows = _rows(f"SELECT {_COLS} FROM memories ORDER BY id DESC LIMIT ?",
                 (min(max(limit, 1), 100),))
    return [_item(r) for r in rows]


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) >= 2}


def _trigrams(text: str) -> Counter:
    flat = " ".join(re.findall(r"\w+", text.lower()))
    return Counter(flat[i:i + 3] for i in range(len(flat) - 2))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


CHAR_ONLY_THRESHOLD = 0.35


def relevant(world: str, question: str, limit: int = 3):
    """Hybrid retrieval over this world's own past work, using only the standard library:
    keyword overlap plus character-trigram cosine similarity (catches word-form variants such
    as evaporate/evaporation and works for any script, including Persian). It is a lexical
    approximation of semantic search, not an embedding model. Ties favour recency."""
    q = _tokens(question)
    if not q:
        return []
    q_grams = _trigrams(question)
    rows = _rows(f"SELECT {_COLS} FROM memories WHERE world=? AND COALESCE(kind,'experience')!='failure' "
                 "ORDER BY id DESC LIMIT 200", (world,))
    scored = []
    for r in rows:
        overlap = len(q & _tokens(r[2])) / len(q)
        cosine = _cosine(q_grams, _trigrams(r[2]))
        if overlap > 0 or cosine >= CHAR_ONLY_THRESHOLD:
            scored.append((0.6 * overlap + 0.4 * cosine, r[0], r))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [_item(s[2]) for s in scored[:limit]]


def prune(max_per_world: int = 500, max_failures: int = 100) -> int:
    """Controlled cleanup: keep the newest experiences per world and the newest failures.
    Experiments and decisions are small and always kept."""
    deleted = 0
    conn = _db()
    try:
        with conn:
            worlds = [r[0] for r in conn.execute("SELECT DISTINCT world FROM memories")]
            for w in worlds:
                cur = conn.execute(
                    "DELETE FROM memories WHERE world=? AND COALESCE(kind,'experience')='experience' AND id NOT IN "
                    "(SELECT id FROM memories WHERE world=? AND COALESCE(kind,'experience')='experience' "
                    "ORDER BY id DESC LIMIT ?)", (w, w, max_per_world))
                deleted += cur.rowcount
            cur = conn.execute(
                "DELETE FROM memories WHERE kind='failure' AND id NOT IN "
                "(SELECT id FROM memories WHERE kind='failure' ORDER BY id DESC LIMIT ?)", (max_failures,))
            deleted += cur.rowcount
    finally:
        conn.close()
    return deleted


def latest_of_kind(kind: str, limit: int = 2):
    """Most recent memories of one kind, regardless of keyword overlap."""
    rows = _rows(f"SELECT {_COLS} FROM memories WHERE kind=? ORDER BY id DESC LIMIT ?",
                 (kind, min(max(limit, 1), 20)))
    return [_item(r) for r in rows]


def stats() -> dict:
    """Counts per world and per kind, for the dashboard."""
    total = _rows("SELECT COUNT(*) FROM memories")[0][0]
    by_world = {r[0]: r[1] for r in _rows("SELECT world, COUNT(*) FROM memories GROUP BY world")}
    by_kind = {(r[0] or "experience"): r[1]
               for r in _rows("SELECT kind, COUNT(*) FROM memories GROUP BY kind")}
    return {"total": total, "by_world": by_world, "by_kind": by_kind}


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
