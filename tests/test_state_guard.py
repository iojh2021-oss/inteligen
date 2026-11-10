import json
import sqlite3

import pytest

from app import learning, memory, state_guard
from app.worlds import WORLDS


def test_atomic_write_keeps_the_old_file_if_serialization_fails(tmp_path):
    path = tmp_path / "state.json"
    state_guard.atomic_write_json(path, {"ok": 1})
    with pytest.raises(TypeError):
        state_guard.atomic_write_json(path, {"bad": object()})
    assert json.loads(path.read_text()) == {"ok": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_a_healthy_state_validates_and_a_fresh_start_is_valid(db):
    assert state_guard.validate_state(str(db / "docs")) == []
    memory.save("knowledge", "p", "r")
    learning.record_status({"status": "complete", "successful_worlds": list(WORLDS),
                            "timestamp": "2026-01-01T00:00:00", "request_id": "r1"})
    assert state_guard.validate_state(str(db / "docs")) == []


def test_invalid_json_is_reported(db):
    evo = db / "evolution"
    evo.mkdir()
    (evo / "history.json").write_text("{not json")
    assert any("history.json" in p for p in state_guard.validate_state(str(db / "docs")))


def test_inconsistent_counters_are_reported(db):
    learning.record_status({"status": "complete", "successful_worlds": list(WORLDS)})
    path = db / "evolution" / "status.json"
    data = json.loads(path.read_text())
    data["per_world"]["science"]["ok"] += 5
    path.write_text(json.dumps(data))
    assert any("science" in p for p in state_guard.validate_state(str(db / "docs")))


def corrupt(path):
    path.write_bytes(b"this is not a sqlite database" * 50)


def test_corrupt_memory_is_restored_from_the_verified_backup(db):
    memory.save("knowledge", "entropy", "good record")
    assert state_guard.backup_memory() is True
    corrupt(db / "memory.sqlite3")
    assert state_guard.db_ok(db / "memory.sqlite3") is False
    message = state_guard.recover_if_needed()
    assert "restored from backup" in message
    assert memory.recent(5)[0]["result"] == "good record"


def test_corrupt_memory_without_backup_starts_fresh_and_says_so(db):
    memory.save("knowledge", "entropy", "record")
    corrupt(db / "memory.sqlite3")
    assert "fresh memory" in state_guard.recover_if_needed()
    assert memory.recent(5) == []


def test_backup_is_never_taken_from_a_corrupt_database(db):
    memory.save("knowledge", "p", "r")
    state_guard.backup_memory()
    corrupt(db / "memory.sqlite3")
    assert state_guard.backup_memory() is False
    assert state_guard.db_ok(str(db / "memory.sqlite3") + ".bak")
