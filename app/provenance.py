"""Evidence provenance and validation rules for structured experiences.

A digest is an integrity fingerprint, not proof that a source is authentic.
Reviewer labels are audit metadata; this app does not authenticate reviewers.
"""
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone

from app import memory

SOURCE_TYPES = {"manual_observation", "external_reference", "simulation", "model_generated", "unknown"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS experience_provenance (
        experience_id INTEGER PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_reference TEXT,
        reviewer_label TEXT,
        evidence_sha256 TEXT NOT NULL,
        validation_status TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")


def _text(value, field, maximum, required=False):
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{field} must be a non-empty string of at most {maximum} characters" if required
                         else f"{field} must be a string of at most {maximum} characters")
    return value.strip() or None


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
    """Resolve once, storing the outcome and its evidence metadata atomically."""
    if outcome_status not in {"confirmed", "refuted", "inconclusive"}:
        raise ValueError("outcome_status must be confirmed, refuted, or inconclusive")
    observed_outcome = _text(observed_outcome, "observed_outcome", 4000, True)
    evidence_note = _text(evidence_note, "evidence_note", 4000)
    evidence_reference = _text(evidence_reference, "evidence_reference", 1000)
    reviewer_label = _text(reviewer_label, "reviewer_label", 120)
    if evidence_source_type not in SOURCE_TYPES:
        raise ValueError("evidence_source_type must be one of: " + ", ".join(sorted(SOURCE_TYPES)))
    if observed_value is not None:
        observed_value = float(observed_value)
        if not math.isfinite(observed_value):
            raise ValueError("observed_value must be finite")

    if evidence_source_type in {"simulation", "model_generated", "unknown"} and outcome_status != "inconclusive":
        raise ValueError(f"{evidence_source_type} evidence can only produce an inconclusive outcome")
    if outcome_status in {"confirmed", "refuted"}:
        if evidence_source_type not in {"manual_observation", "external_reference"}:
            raise ValueError("confirmed/refuted outcomes require manual_observation or external_reference evidence")
        if not evidence_note or not reviewer_label:
            raise ValueError("confirmed/refuted outcomes require evidence_note and reviewer_label")
        if evidence_source_type == "external_reference" and not evidence_reference:
            raise ValueError("external_reference evidence requires evidence_reference")

    payload = {
        "experience_id": int(experience_id),
        "observed_outcome": observed_outcome,
        "observed_value": observed_value,
        "evidence_note": evidence_note,
        "evidence_source_type": evidence_source_type,
        "evidence_reference": evidence_reference,
        "reviewer_label": reviewer_label,
        "outcome_status": outcome_status,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    validation_status = (
        "reviewed" if outcome_status in {"confirmed", "refuted"}
        else "simulation_only" if evidence_source_type == "simulation"
        else "unverified"
    )

    conn = memory._db()
    try:
        _ensure_table(conn)
        with conn:
            cur = conn.execute(
                """UPDATE experiences
                   SET observed_outcome=?, observed_value=?, outcome_status=?,
                       evidence_note=?, resolved_at=?
                   WHERE id=? AND outcome_status='planned'""",
                (observed_outcome, observed_value, outcome_status, evidence_note,
                 _now(), int(experience_id)),
            )
            if cur.rowcount != 1:
                raise ValueError("Experience not found or already resolved")
            row = conn.execute(
                f"SELECT {memory._EXPERIENCE_COLS} FROM experiences WHERE id=?",
                (int(experience_id),),
            ).fetchone()
            conn.execute(
                """INSERT INTO experience_provenance(
                    experience_id,source_type,source_reference,reviewer_label,
                    evidence_sha256,validation_status,created_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (int(experience_id), evidence_source_type, evidence_reference,
                 reviewer_label, digest, validation_status, _now()),
            )
    finally:
        conn.close()

    item = memory._experience_item(row)
    try:
        memory._index_experience(int(experience_id), item["world"], memory._experience_text(item))
    except memory.semantic.SemanticUnavailable:
        pass
    item["provenance"] = {
        "source_type": evidence_source_type,
        "source_reference": evidence_reference,
        "reviewer_label": reviewer_label,
        "evidence_sha256": digest,
        "validation_status": validation_status,
        "reviewer_authenticated": False,
    }
    return item


def enrich(items: list[dict]) -> list[dict]:
    """Attach provenance metadata without changing world-scoped retrieval."""
    if not items:
        return []
    ids = [int(item["id"]) for item in items]
    placeholders = ",".join("?" for _ in ids)
    conn = memory._db()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            f"""SELECT experience_id,source_type,source_reference,reviewer_label,
                       evidence_sha256,validation_status,created_at
                FROM experience_provenance WHERE experience_id IN ({placeholders})""",
            ids,
        ).fetchall()
    finally:
        conn.close()
    by_id = {
        row[0]: {
            "source_type": row[1], "source_reference": row[2], "reviewer_label": row[3],
            "evidence_sha256": row[4], "validation_status": row[5],
            "created_at": row[6], "reviewer_authenticated": False,
        }
        for row in rows
    }
    return [{**item, "provenance": by_id.get(int(item["id"]), {
        "source_type": "unknown", "source_reference": None, "reviewer_label": None,
        "evidence_sha256": None, "validation_status": "unverified",
        "reviewer_authenticated": False,
    })} for item in items]


def summary() -> dict:
    conn = memory._db()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            """SELECT e.world,p.source_type,p.validation_status,COUNT(*)
               FROM experiences e LEFT JOIN experience_provenance p ON p.experience_id=e.id
               GROUP BY e.world,p.source_type,p.validation_status"""
        ).fetchall()
    finally:
        conn.close()
    result = {}
    for world in memory.WORLDS:
        result[world] = {"by_source": {}, "by_validation": {}, "records_with_provenance": 0}
    for world, source_type, validation_status, count in rows:
        item = result.setdefault(world, {"by_source": {}, "by_validation": {}, "records_with_provenance": 0})
        source = source_type or "unknown"
        status = validation_status or "unverified"
        item["by_source"][source] = item["by_source"].get(source, 0) + count
        item["by_validation"][status] = item["by_validation"].get(status, 0) + count
        if validation_status:
            item["records_with_provenance"] += count
    return result
