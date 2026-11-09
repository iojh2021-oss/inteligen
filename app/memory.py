"""Durable SQLite memory, world-scoped experience records, and provenance."""
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.retrieval import rank_rows
from app import semantic
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
    conn.execute("""CREATE TABLE IF NOT EXISTS semantic_embeddings (
        memory_id INTEGER PRIMARY KEY,
        world TEXT NOT NULL,
        model_version TEXT NOT NULL,
        vector_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS semantic_experience_embeddings (
        experience_id INTEGER PRIMARY KEY,
        world TEXT NOT NULL,
        model_version TEXT NOT NULL,
        vector_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
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


def _index_memory(memory_id: int, world: str, prompt: str) -> list[float] | bool:
    if not semantic.enabled():
        return False
    vector = semantic.embed_text(prompt)
    import json
    conn = _db()
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO semantic_embeddings(
                    memory_id,world,model_version,vector_json,created_at
                ) VALUES(?,?,?,?,?)""",
                (memory_id, world, semantic.MODEL_VERSION,
                 json.dumps(vector, separators=(",", ":")), _now()),
            )
        return vector
    finally:
        conn.close()




def _index_experience(experience_id: int, world: str, text: str) -> list[float] | bool:
    if not semantic.enabled():
        return False
    vector = semantic.embed_text(text)
    import json
    conn = _db()
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO semantic_experience_embeddings(
                    experience_id,world,model_version,vector_json,created_at
                ) VALUES(?,?,?,?,?)""",
                (experience_id, world, semantic.MODEL_VERSION,
                 json.dumps(vector, separators=(",", ":")), _now()),
            )
        return vector
    finally:
        conn.close()


def _experience_text(item: dict) -> str:
    return " ".join(str(item.get(key) or "") for key in (
        "hypothesis", "prediction", "observed_outcome", "evidence_note"
    ))[:8000]


def save(world: str, prompt: str, result: str, request_id: str = None):
    conn = _db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO memories(world,prompt,result,created_at,request_id) VALUES(?,?,?,?,?)",
                (world, prompt[:8000], result[:12000], _now(), request_id),
            )
            memory_id = int(cur.lastrowid)
    finally:
        conn.close()
    # Embedding failure must never prevent the primary memory record from saving.
    try:
        _index_memory(memory_id, world, prompt[:8000])
    except semantic.SemanticUnavailable:
        pass
    return memory_id


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
    """Hybrid retrieval: BM25 + multilingual dense cosine ranking, with BM25 fallback."""
    rows = _rows(
        f"SELECT {_COLS} FROM memories WHERE world=? ORDER BY id DESC LIMIT 200",
        (world,),
    )
    lexical = rank_rows(rows, question, max(limit, 1))
    if not semantic.enabled() or not rows:
        return [_item(row) for row in lexical]

    try:
        import json
        query_vector = semantic.embed_text(question)
        ids = [int(row[0]) for row in rows]
        placeholders = ",".join("?" for _ in ids)
        indexed = _rows(
            f"""SELECT memory_id,vector_json FROM semantic_embeddings
                WHERE world=? AND model_version=? AND memory_id IN ({placeholders})""",
            (world, semantic.MODEL_VERSION, *ids),
        )
        vectors = {int(row[0]): json.loads(row[1]) for row in indexed}
        by_id = {int(row[0]): row for row in rows}
        for row in rows:
            memory_id = int(row[0])
            if memory_id not in vectors:
                try:
                    vector = _index_memory(memory_id, world, row[2])
                    if vector:
                        vectors[memory_id] = vector
                except semantic.SemanticUnavailable:
                    continue
        dense = semantic.rank_documents(
            query_vector,
            [(memory_id, vector) for memory_id, vector in vectors.items()
             if memory_id in by_id],
        )
        if not dense:
            return [_item(row) for row in lexical]
        # Reciprocal-rank fusion avoids comparing raw BM25 and cosine scales.
        fused = {}
        for rank, row in enumerate(lexical, start=1):
            fused[int(row[0])] = fused.get(int(row[0]), 0.0) + 1.0 / (60 + rank)
        for rank, (memory_id, _score) in enumerate(dense, start=1):
            fused[memory_id] = fused.get(memory_id, 0.0) + 1.0 / (60 + rank)
        ordered = sorted(fused, key=lambda memory_id: (fused[memory_id], memory_id), reverse=True)
        return [_item(by_id[memory_id]) for memory_id in ordered[:max(limit, 1)]]
    except semantic.SemanticUnavailable:
        return [_item(row) for row in lexical]


def backfill_semantic(limit: int = 500) -> dict:
    """Index recent historical memories once; existing records remain usable if disabled."""
    if not semantic.enabled():
        return {"enabled": False, "indexed": 0, "pending": 0, "model": semantic.MODEL_VERSION}
    rows = _rows(
        f"""SELECT m.{_COLS.replace(',', ', m.').replace('id,', 'id,')} FROM memories m
            LEFT JOIN semantic_embeddings e ON e.memory_id=m.id
                AND e.model_version=?
            WHERE e.memory_id IS NULL ORDER BY m.id DESC LIMIT ?""",
        (semantic.MODEL_VERSION, min(max(int(limit), 1), 2000)),
    )
    indexed_memories = 0
    indexed_experiences = 0
    failed = 0
    for row in rows:
        try:
            indexed_memories += int(bool(_index_memory(int(row[0]), row[1], row[2])))
        except semantic.SemanticUnavailable:
            failed += 1
            break

    experience_rows = _rows(
        """SELECT x.id,x.world,x.request_id,x.hypothesis,x.prediction,x.expected_metric,
                  x.predicted_value,x.observed_outcome,x.observed_value,x.outcome_status,
                  x.confidence,x.evidence_note,x.created_at,x.resolved_at
           FROM experiences x
           LEFT JOIN semantic_experience_embeddings e ON e.experience_id=x.id
               AND e.model_version=?
           WHERE e.experience_id IS NULL ORDER BY x.id DESC LIMIT ?""",
        (semantic.MODEL_VERSION, min(max(int(limit), 1), 2000)),
    )
    if not failed:
        for row in experience_rows:
            try:
                item = _experience_item(row)
                indexed_experiences += int(bool(_index_experience(
                    int(row[0]), row[1], _experience_text(item)
                )))
            except semantic.SemanticUnavailable:
                failed += 1
                break

    pending_memory_rows = _rows(
        """SELECT COUNT(*) FROM memories m
           LEFT JOIN semantic_embeddings e ON e.memory_id=m.id
               AND e.model_version=?
           WHERE e.memory_id IS NULL""",
        (semantic.MODEL_VERSION,),
    )
    pending_experience_rows = _rows(
        """SELECT COUNT(*) FROM experiences x
           LEFT JOIN semantic_experience_embeddings e ON e.experience_id=x.id
               AND e.model_version=?
           WHERE e.experience_id IS NULL""",
        (semantic.MODEL_VERSION,),
    )
    pending_memories = int(pending_memory_rows[0][0])
    pending_experiences = int(pending_experience_rows[0][0])
    return {
        "enabled": True,
        "indexed": indexed_memories + indexed_experiences,
        "indexed_memories": indexed_memories,
        "indexed_experiences": indexed_experiences,
        "pending": pending_memories + pending_experiences,
        "pending_memories": pending_memories,
        "pending_experiences": pending_experiences,
        "failed": failed, "model": semantic.MODEL_VERSION,
    }


def semantic_summary() -> dict:
    conn = _db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM semantic_embeddings WHERE model_version=?",
            (semantic.MODEL_VERSION,),
        ).fetchone()[0]
        experience_count = conn.execute(
            "SELECT COUNT(*) FROM semantic_experience_embeddings WHERE model_version=?",
            (semantic.MODEL_VERSION,),
        ).fetchone()[0]
    finally:
        conn.close()
    configured = semantic.enabled()
    loaded = semantic.model_loaded()
    return {
        "enabled": configured,
        "model_loaded": loaded,
        "model": semantic.MODEL_VERSION,
        "dimension": semantic.DIMENSION,
        "indexed_memories": int(count),
        "indexed_experiences": int(experience_count),
        "retrieval": "hybrid-bm25-dense" if configured and loaded else "bm25-fallback",
    }


def forget(memory_id: int) -> bool:
    conn = _db()
    try:
        with conn:
            cur = conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            if cur.rowcount:
                conn.execute("DELETE FROM semantic_embeddings WHERE memory_id=?", (memory_id,))
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
            experience_id = int(cur.lastrowid)
    finally:
        conn.close()
    try:
        _index_experience(experience_id, world, hypothesis.strip() + " " + prediction.strip())
    except semantic.SemanticUnavailable:
        pass
    return experience_id


def resolve_experience(
    experience_id: int,
    observed_outcome: str,
    outcome_status: str,
    observed_value: float = None,
    evidence_note: str = None,
    evidence_source_type: str = "unknown",
    evidence_reference: str = None,
    reviewer_label: str = None,
) -> dict:
    """Compatibility entry point that enforces the provenance validation layer."""
    from app import provenance

    return provenance.resolve_experience(
        experience_id=experience_id,
        observed_outcome=observed_outcome,
        outcome_status=outcome_status,
        observed_value=observed_value,
        evidence_note=evidence_note,
        evidence_source_type=evidence_source_type,
        evidence_reference=evidence_reference,
        reviewer_label=reviewer_label,
    )


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
        lexical = rank_rows(rankable, question, limit)
        fused = {}
        for rank, item in enumerate(lexical, start=1):
            fused[int(item[0])] = fused.get(int(item[0]), 0.0) + 1.0 / (60 + rank)

        if semantic.enabled() and rows:
            try:
                import json
                query_vector = semantic.embed_text(question)
                ids = [int(row[0]) for row in rows]
                placeholders = ",".join("?" for _ in ids)
                indexed = _rows(
                    f"""SELECT experience_id,vector_json
                        FROM semantic_experience_embeddings
                        WHERE world=? AND model_version=? AND experience_id IN ({placeholders})""",
                    (world, semantic.MODEL_VERSION, *ids),
                )
                vectors = {int(item[0]): json.loads(item[1]) for item in indexed}
                by_id = {int(row[0]): row for row in rows}
                for row in rows:
                    experience_id = int(row[0])
                    if experience_id not in vectors:
                        try:
                            item = _experience_item(row)
                            vector = _index_experience(
                                experience_id, world, _experience_text(item)
                            )
                            if vector:
                                vectors[experience_id] = vector
                        except semantic.SemanticUnavailable:
                            continue
                dense = semantic.rank_documents(
                    query_vector,
                    [(item_id, vector) for item_id, vector in vectors.items()
                     if item_id in by_id],
                )
                for rank, (experience_id, _score) in enumerate(dense, start=1):
                    fused[experience_id] = fused.get(experience_id, 0.0) + 1.0 / (60 + rank)
                if fused:
                    ordered_ids = sorted(
                        fused, key=lambda item_id: (fused[item_id], item_id), reverse=True
                    )[:limit]
                    rows = [by_id[item_id] for item_id in ordered_ids]
                else:
                    rows = [by_id[int(item[0])] for item in lexical]
            except semantic.SemanticUnavailable:
                selected_ids = {item[0] for item in lexical}
                rows = [row for row in rows if row[0] in selected_ids]
                rows.sort(key=lambda row: next(i for i, item in enumerate(lexical) if item[0] == row[0]))
        else:
            selected_ids = {item[0] for item in lexical}
            rows = [row for row in rows if row[0] in selected_ids]
            rows.sort(key=lambda row: next(i for i, item in enumerate(lexical) if item[0] == row[0]))
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
