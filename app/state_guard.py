"""State integrity: atomic writes, validation, backup and recovery of the durable state.

The runner is temporary, so everything that must survive lives in files that are restored from
the state branch at the start of a run and pushed back at the end. A corrupt state must never
be pushed over a healthy one.
"""
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from app import config
from app.worlds import WORLDS


def atomic_write_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_json(path, data, indent: int = 2) -> None:
    # Serialize first: a non-serializable value must not touch the existing file.
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=indent) + "\n")


def db_ok(path) -> bool:
    path = Path(path)
    if not path.exists():
        return True  # a fresh start is valid
    try:
        conn = sqlite3.connect(path)
        try:
            return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def _bak(path) -> Path:
    return Path(str(path) + ".bak")


def backup_memory() -> bool:
    """Keep one verified copy of the memory database (restored by recover_if_needed)."""
    path = Path(config.database_path())
    if not path.exists() or not db_ok(path):
        return False
    tmp = Path(str(path) + ".bak.tmp")
    src = sqlite3.connect(path)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    os.replace(tmp, _bak(path))
    return True


def recover_if_needed():
    """If the database is corrupt, restore the verified backup. Returns a message or None."""
    path = Path(config.database_path())
    if db_ok(path):
        return None
    bak = _bak(path)
    corrupt = Path(str(path) + ".corrupt")
    shutil.move(str(path), str(corrupt))
    if db_ok(bak) and bak.exists():
        shutil.copyfile(bak, path)
        return "memory database was corrupt; restored from backup"
    return "memory database was corrupt and no valid backup exists; started a fresh memory"


def _json_problem(path: Path):
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"{path}: invalid JSON ({exc})"
    return None


def validate_state(state_dir: str = "docs/state") -> list:
    """Return a list of problems; an empty list means the state is consistent."""
    problems = []
    if not db_ok(config.database_path()):
        problems.append("memory database failed its integrity check")
    evo = Path(config.evolution_dir())
    files = [evo / "stable.json", evo / "history.json", evo / "status.json"]
    files += sorted((evo / "versions").glob("*.json")) if (evo / "versions").exists() else []
    files += sorted((evo / "proposals").glob("*.json")) if (evo / "proposals").exists() else []
    files += sorted(Path(state_dir).glob("*.json")) if Path(state_dir).exists() else []
    for f in files:
        if f.exists():
            issue = _json_problem(f)
            if issue:
                problems.append(issue)
    if problems:
        return problems
    history = evo / "history.json"
    if history.exists() and not isinstance(json.loads(history.read_text(encoding="utf-8")), list):
        problems.append("history.json must be a list")
    status = evo / "status.json"
    if status.exists():
        data = json.loads(status.read_text(encoding="utf-8"))
        total = data.get("cycles_total", 0)
        for name in WORLDS:
            w = (data.get("per_world") or {}).get(name)
            if w is None or w.get("ok", 0) + w.get("fail", 0) != total:
                problems.append(f"status counters inconsistent for world '{name}'")
        if data.get("cycles_complete", 0) + data.get("cycles_partial", 0) \
                + data.get("cycles_failed", 0) != total:
            problems.append("status cycle counters do not add up")
    return problems
