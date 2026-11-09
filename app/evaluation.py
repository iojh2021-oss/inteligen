"""Deterministic, explainable quality signals for Inteligen world outputs.

This is a rubric-based coverage check, not a measure of truth, intelligence, or learning.
It deliberately reports observable text signals and missing criteria for human review.
"""
import re

RUBRICS = {
    "knowledge": {
        "concepts": (r"concept|definition|means|refers to|مفهوم|تعریف|یعنی",),
        "fact_vs_assumption": (r"assumption|inference|fact|verified|فرض|واقعیت|استنباط",),
        "uncertainty": (r"uncertain|uncertainty|unknown|confidence|نامطمئن|عدم قطعیت|نامشخص",),
        "evidence_limits": (r"evidence|source|citation|منبع|شواهد|محدودیت",),
    },
    "reasoning": {
        "ordered_steps": (r"step|first|second|therefore|گام|مرحله|ابتدا|بنابراین",),
        "assumptions": (r"assumption|premise|فرض|پیش‌فرض",),
        "countercheck": (r"counterexample|alternative|falsif|برخلاف|مثال نقض|جایگزین",),
        "conclusion": (r"conclusion|result|نتیجه|جمع‌بندی",),
    },
    "science": {
        "hypothesis": (r"hypothesis|hypotheses|فرضیه",),
        "prediction": (r"predict|prediction|expected|پیش‌بینی|انتظار",),
        "test": (r"experiment|test|measure|آزمایش|آزمون|اندازه‌گیری",),
        "limitations": (r"limitation|limit|risk|محدودیت|ریسک",),
    },
    "creativity": {
        "multiple_ideas": (r"idea|option|approach|alternative|ایده|گزینه|راهکار|رویکرد",),
        "tradeoffs": (r"trade.?off|advantage|disadvantage|pros|cons|مزیت|عیب|مبادله",),
        "original_combination": (r"combine|adapt|reframe|ترکیب|بازطراحی|تلفیق",),
        "practicality": (r"practical|feasible|implement|عملی|امکان‌پذیر|اجرا",),
    },
    "learning": {
        "identified_gap": (r"gap|weakness|missing|ضعف|شکاف|کمبود",),
        "measurable_metric": (r"metric|measure|score|rate|عدد|شاخص|امتیاز|نرخ",),
        "evaluation_test": (r"evaluate|evaluation|benchmark|test|ارزیابی|معیار|آزمون",),
        "improvement": (r"improve|improvement|next iteration|بهبود|تکرار بعدی",),
    },
}

def evaluate_text(world: str, output: str) -> dict:
    """Return transparent criterion hits; never interpret this as factual correctness."""
    rubric = RUBRICS.get(world)
    if rubric is None:
        raise ValueError(f"Unknown world: {world}")
    text = str(output or "")
    normalized = text.casefold()
    checks = {
        criterion: any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)
        for criterion, patterns in rubric.items()
    }
    passed = sum(checks.values())
    total = len(checks)
    return {
        "world": world,
        "score": round(100 * passed / total),
        "passed": passed,
        "total": total,
        "checks": checks,
        "missing": [name for name, ok in checks.items() if not ok],
        "output_chars": len(text),
        "output_words": len(re.findall(r"\w+", text, flags=re.UNICODE)),
        "interpretation": "textual rubric coverage only; not truth, correctness, intelligence, or learning",
    }

def evaluate_worlds(outputs: dict) -> dict:
    results = {}
    for world in RUBRICS:
        value = outputs.get(world, "")
        if str(value).startswith("(unavailable:"):
            results[world] = {"world": world, "status": "unavailable", "score": None,
                              "missing": list(RUBRICS[world]), "output_chars": 0}
        else:
            results[world] = {"status": "evaluated", **evaluate_text(world, str(value))}
    available = [v["score"] for v in results.values() if v["score"] is not None]
    return {
        "rubric_version": 1,
        "scope": "deterministic text-coverage signals; human review still required",
        "overall_score": round(sum(available) / len(available)) if available else None,
        "evaluated_worlds": len(available),
        "worlds": results,
    }


# Persisted, versioned evaluation snapshots. Scores remain structural proxies.
EVALUATION_SCHEMA_VERSION = 1


def _evaluation_db():
    import sqlite3
    from pathlib import Path
    from app import config

    path = Path(config.database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS evaluation_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rubric_version INTEGER NOT NULL,
        world TEXT NOT NULL,
        score REAL,
        status TEXT NOT NULL,
        checks_json TEXT NOT NULL,
        output_chars INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def record_evaluation(report: dict) -> dict:
    """Persist per-world rubric results and return a versioned snapshot id."""
    import json
    from datetime import datetime, timezone

    conn = _evaluation_db()
    ids = {}
    try:
        with conn:
            for world, result in report["worlds"].items():
                cur = conn.execute(
                    """INSERT INTO evaluation_snapshots(
                        rubric_version,world,score,status,checks_json,output_chars,created_at
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (report["rubric_version"], world, result.get("score"),
                     result.get("status", "evaluated"),
                     json.dumps(result.get("checks", {}), sort_keys=True),
                     int(result.get("output_chars", 0)),
                     datetime.now(timezone.utc).isoformat()),
                )
                ids[world] = int(cur.lastrowid)
    finally:
        conn.close()
    return {"snapshot_ids": ids, "rubric_version": report["rubric_version"]}


def evaluation_history(limit: int = 100) -> dict:
    """Return latest records and per-world change from the preceding recorded score."""
    import json

    limit = min(max(int(limit), 1), 500)
    conn = _evaluation_db()
    try:
        rows = conn.execute(
            """SELECT id,rubric_version,world,score,status,checks_json,output_chars,created_at
               FROM evaluation_snapshots ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    latest = {}
    previous = {}
    for row in rows:
        world = row[2]
        if world not in latest:
            latest[world] = row
        elif world not in previous and row[3] is not None:
            previous[world] = row

    worlds = {}
    for world, row in latest.items():
        prior = previous.get(world)
        worlds[world] = {
            "latest": {
                "id": row[0], "rubric_version": row[1], "score": row[3],
                "status": row[4], "checks": json.loads(row[5]),
                "output_chars": row[6], "created_at": row[7],
            },
            "previous_score": prior[3] if prior else None,
            "score_delta": round(row[3] - prior[3], 2)
                if prior and row[3] is not None and prior[3] is not None
                and row[1] == prior[1] else None,
        }
    return {
        "scope": "structural rubric coverage only; not factual correctness or intelligence",
        "worlds": worlds,
    }
