"""Continuous-learning bookkeeping for scheduled GitHub Actions cycles.

- status.json: consistent counters, overall and per world (each world has its own history).
- curriculum: a rotating list of topics so cycles do not repeat the same question.
- coaching: each world is told which criteria *its own* recent outputs kept missing.
This is learning by context and memory across cycles. Model weights are never trained.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app import config, state_guard
from app.worlds import WORLDS

WINDOW = 3
CADENCE_HOURS = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dir() -> Path:
    return Path(config.evolution_dir())


def load_history() -> list:
    path = _dir() / "history.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def default_status() -> dict:
    return {
        "schema_version": 1, "cycles_total": 0, "cycles_complete": 0, "cycles_partial": 0,
        "cycles_failed": 0, "cadence_hours": CADENCE_HOURS, "last_run_at": None,
        "last_complete_at": None, "last_request_id": None, "last_error": None,
        "per_world": {w: {"runs": 0, "ok": 0, "fail": 0, "last_ok_at": None,
                          "last_score": None, "best_score": None, "last_missing": []}
                      for w in WORLDS},
    }


def load_status() -> dict:
    path = _dir() / "status.json"
    base = default_status()
    if not path.exists():
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return base
    base.update({k: v for k, v in data.items() if k != "per_world"})
    for w in WORLDS:
        base["per_world"][w].update((data.get("per_world") or {}).get(w, {}))
    return base


def _save_status(status: dict) -> None:
    state_guard.atomic_write_json(_dir() / "status.json", status)


def record_status(state: dict) -> dict:
    """Count one finished cycle. state is the cycle's latest.json payload."""
    status = load_status()
    now = state.get("timestamp") or _now()
    ok_worlds = set(state.get("successful_worlds") or [])
    scores = (state.get("evaluation") or {}).get("worlds", {})
    status["cycles_total"] += 1
    complete = state.get("status") == "complete"
    status["cycles_complete" if complete else "cycles_partial"] += 1
    status["last_run_at"] = now
    status["last_request_id"] = state.get("request_id")
    status["last_error"] = None
    if complete:
        status["last_complete_at"] = now
    for w in WORLDS:
        item = status["per_world"][w]
        item["runs"] += 1
        if w in ok_worlds:
            item["ok"] += 1
            item["last_ok_at"] = now
            score = (scores.get(w) or {}).get("score")
            if score is not None:
                item["last_score"] = score
                item["best_score"] = score if item["best_score"] is None else max(item["best_score"], score)
                item["last_missing"] = (scores.get(w) or {}).get("missing", [])
        else:
            item["fail"] += 1
    _save_status(status)
    return status


def record_failed_cycle(error: str) -> dict:
    """A cycle that produced no usable result still counts, so counters stay honest."""
    status = load_status()
    status["cycles_total"] += 1
    status["cycles_failed"] += 1
    status["last_run_at"] = _now()
    status["last_error"] = str(error)[:300]
    for w in WORLDS:
        status["per_world"][w]["runs"] += 1
        status["per_world"][w]["fail"] += 1
    _save_status(status)
    return status


# ---- curriculum ----------------------------------------------------------------------

def load_curriculum() -> list:
    path = _dir() / "curriculum.json"
    if not path.exists():
        path = Path(__file__).resolve().parent.parent / "evolution" / "curriculum.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [t["question"] for t in data["topics"] if isinstance(t.get("question"), str)]


def pick_topic(cycles_total: int) -> str:
    topics = load_curriculum()
    return topics[cycles_total % len(topics)]


# ---- per-world coaching --------------------------------------------------------------

def coaching(world: str, history: list = None, version: int = None) -> str:
    """Tell a world which criteria its own recent outputs missed (empty if none)."""
    history = load_history() if history is None else history
    recent = []
    for entry in history:
        if version is not None and entry.get("config_version") != version:
            continue
        item = (entry.get("worlds") or {}).get(world) or {}
        if item.get("score") is not None:
            recent.append(item)
    recent = recent[-WINDOW:]
    if not recent:
        return ""
    counts = {}
    for item in recent:
        for criterion in item.get("missing", []):
            counts[criterion] = counts.get(criterion, 0) + 1
    repeated = sorted(c for c, n in counts.items() if n >= max(1, (len(recent) + 1) // 2))
    if not repeated:
        return ""
    names = ", ".join(c.replace("_", " ") for c in repeated)
    return (f"In your last {len(recent)} evaluated cycles you often missed: {names}. "
            "Cover these explicitly this time.")
