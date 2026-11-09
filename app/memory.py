"""Durable SQLite memory with provenance (request_id, world, timestamp), per-world
retrieval, forgetting, and per-world capability metrics."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.retrieval import rank_rows


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


def relevant(world: str, question: str, limit: int = 3):
    """Retrieve this world's best lexical matches using BM25-style ranking.

    This is explainable keyword retrieval, not semantic/vector search. Results
    remain isolated by world and retain timestamps and request provenance.
    """
    rows = _rows(
        f"SELECT {_COLS} FROM memories WHERE world=? ORDER BY id DESC LIMIT 200",
        (world,),
    )
    return [_item(row) for row in rank_rows(rows, question, limit)]


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
