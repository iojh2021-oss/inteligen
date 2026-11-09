"""Durable SQLite memory, world-scoped experience records, and provenance."""
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.retrieval import rank_rows
from app.worlds import WORLDS

EXPERIENCE_STATUSES = {"planned", "confirmed", "refuted", "inconclusive"}


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
    conn.execute("""CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        world TEXT NOT NULL,
        request_id TEXT,
        hypothesis TEXT NOT NULL,
        prediction TEXT NOT NULL,
        expected_metric TEXT,
        predicted_value REAL,
        observed_outcome TEXT,
        observed_value REAL,
        outcome_status TEXT NOT NULL,
        confidence REAL,
        evidence_note TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT
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
_EXPERIENCE_COLS = (
    "id,world,request_id,hypothesis,prediction,expected_metric,predicted_value,"
    "observed_outcome,observed_value,outcome_status,confidence,evidence_note,created_at,resolved_at"
)


def recent(limit: int = 20):
    rows = _rows(f"SELECT {_COLS} FROM memories ORDER BY id DESC LIMIT ?",
                 (min(max(limit, 1), 100),))
    return [_item(r) for r in rows]


def relevant(world: str, question: str, limit: int = 3):
    """Retrieve this world's best lexical matches; this is not semantic search."""
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


def _experience_item(row) -> dict:
    keys = (
        "id", "world", "request_id", "hypothesis", "prediction", "expected_metric",
        "predicted_value", "observed_outcome", "observed_value", "outcome_status",
        "confidence", "evidence_note", "created_at", "resolved_at",
    )
    item = dict(zip(keys, row))
    if item["predicted_value"] is not None and item["observed_value"] is not None:
        item["absolute_error"] = round(abs(item["predicted_value"] - item["observed_value"]), 6)
    else:
        item["absolute_error"] = None
    return item


def record_experience(
    world: str,
    hypothesis: str,
    prediction: str,
    request_id: str = None,
    expected_metric: str = None,
    predicted_value: float = None,
    confidence: float = None,
) -> int:
    """Record a proposed, testable experience; it is not treated as a proven fact."""
    if world not in WORLDS:
        raise ValueError("Unknown world")
    if not isinstance(hypothesis, str) or not hypothesis.strip() or len(hypothesis) > 4000:
        raise ValueError("hypothesis must contain 1 to 4000 characters")
    if not isinstance(prediction, str) or not prediction.strip() or len(prediction) > 4000:
        raise ValueError("prediction must contain 1 to 4000 characters")
    if expected_metric is not None and (not isinstance(expected_metric, str) or len(expected_metric) > 120):
        raise ValueError("expected_metric must be at most 120 characters")
    if confidence is not None:
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be a finite number between 0 and 1")
    if predicted_value is not None:
        predicted_value = float(predicted_value)
        if not math.isfinite(predicted_value):
            raise ValueError("predicted_value must be finite")
    conn = _db()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO experiences(
                    world,request_id,hypothesis,prediction,expected_metric,predicted_value,
                    outcome_status,confidence,created_at
                ) VALUES(?,?,?,?,?,?, 'planned', ?, ?)""",
                (world, request_id, hypothesis.strip(), prediction.strip(), expected_metric,
                 predicted_value, confidence, _now()),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def resolve_experience(
    experience_id: int,
    observed_outcome: str,
    outcome_status: str,
    observed_value: float = None,
    evidence_note: str = None,
) -> dict:
    """Record an observed result; status is explicitly supplied by the evaluator."""
    if outcome_status not in {"confirmed", "refuted", "inconclusive"}:
        raise ValueError("outcome_status must be confirmed, refuted, or inconclusive")
    if not isinstance(observed_outcome, str) or not observed_outcome.strip() or len(observed_outcome) > 4000:
        raise ValueError("observed_outcome must contain 1 to 4000 characters")
    if evidence_note is not None and (not isinstance(evidence_note, str) or len(evidence_note) > 4000):
        raise ValueError("evidence_note must be at most 4000 characters")
    if observed_value is not None:
        observed_value = float(observed_value)
        if not math.isfinite(observed_value):
            raise ValueError("observed_value must be finite")

    conn = _db()
    try:
        with conn:
            cur = conn.execute(
                """UPDATE experiences
                   SET observed_outcome=?, observed_value=?, outcome_status=?,
                       evidence_note=?, resolved_at=?
                   WHERE id=? AND outcome_status='planned'""",
                (observed_outcome.strip(), observed_value, outcome_status,
                 evidence_note, _now(), experience_id),
            )
            if cur.rowcount != 1:
                raise ValueError("Experience not found or already resolved")
            row = conn.execute(
                f"SELECT {_EXPERIENCE_COLS} FROM experiences WHERE id=?",
                (experience_id,),
            ).fetchone()
            return _experience_item(row)
    finally:
        conn.close()


def experience_history(world: str, question: str = None, limit: int = 5) -> list[dict]:
    """Return only this world's experiences, ranked by hypothesis relevance."""
    if world not in WORLDS:
        raise ValueError("Unknown world")
    limit = min(max(int(limit), 1), 50)
    rows = _rows(
        f"SELECT {_EXPERIENCE_COLS} FROM experiences WHERE world=? ORDER BY id DESC LIMIT 200",
        (world,),
    )
    if question:
        rankable = [
            (row[0], row[1], row[3], " ".join(str(x or "") for x in (row[4], row[7], row[11])), row[12], row[2])
            for row in rows
        ]
        ranked = rank_rows(rankable, question, limit)
        selected_ids = {row[0] for row in ranked}
        rows = [row for row in rows if row[0] in selected_ids]
        rows.sort(key=lambda row: next(i for i, item in enumerate(ranked) if item[0] == row[0]))
    else:
        rows = rows[:limit]
    return [_experience_item(row) for row in rows]


def experience_summary() -> dict:
    """Summarize outcomes and numeric prediction error independently per world."""
    counts = _rows(
        """SELECT world,outcome_status,COUNT(*)
           FROM experiences GROUP BY world,outcome_status"""
    )
    errors = _rows(
        """SELECT world,AVG(ABS(predicted_value-observed_value))
           FROM experiences
           WHERE predicted_value IS NOT NULL AND observed_value IS NOT NULL
           GROUP BY world"""
    )
    summary = {}
    for world in WORLDS:
        summary[world] = {
            "planned": 0, "confirmed": 0, "refuted": 0, "inconclusive": 0,
            "resolved": 0, "mean_absolute_error": None,
        }
    for world, status, count in counts:
        item = summary.setdefault(world, {
            "planned": 0, "confirmed": 0, "refuted": 0, "inconclusive": 0,
            "resolved": 0, "mean_absolute_error": None,
        })
        item[status] = count
        if status != "planned":
            item["resolved"] += count
    for world, error in errors:
        summary.setdefault(world, {
            "planned": 0, "confirmed": 0, "refuted": 0, "inconclusive": 0,
            "resolved": 0, "mean_absolute_error": None,
        })["mean_absolute_error"] = round(error, 6)
    return summary
