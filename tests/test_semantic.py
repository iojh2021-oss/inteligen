import pytest

from app import memory, semantic


def _vector(index):
    values = [0.0] * semantic.DIMENSION
    values[index] = 1.0
    return values


def test_semantic_retrieval_finds_related_wording_without_lexical_overlap(db, monkeypatch):
    monkeypatch.setattr(semantic, "enabled", lambda: True)

    def fake_embed(text):
        if text in {"solar energy", "sunlight power"}:
            return _vector(0)
        return _vector(1)

    monkeypatch.setattr(semantic, "embed_text", fake_embed)
    memory.save("knowledge", "solar energy", "A stored note about energy from the sun")
    results = memory.relevant("knowledge", "sunlight power", limit=1)
    assert len(results) == 1
    assert results[0]["prompt"] == "solar energy"


def test_semantic_backfill_indexes_older_memories(db, monkeypatch):
    monkeypatch.setattr(semantic, "enabled", lambda: False)
    memory.save("science", "thermal conductivity", "A stored science note")
    memory.save("science", "heat transfer", "Another stored note")

    monkeypatch.setattr(semantic, "enabled", lambda: True)
    monkeypatch.setattr(semantic, "embed_text", lambda text: _vector(2))
    result = memory.backfill_semantic(limit=10)

    assert result["enabled"] is True
    assert result["indexed"] == 2
    assert result["pending"] == 0
    assert memory.semantic_summary()["indexed_memories"] == 2


def test_semantic_failure_falls_back_to_bm25(db, monkeypatch):
    monkeypatch.setattr(semantic, "enabled", lambda: True)
    memory.save("knowledge", "entropy in thermodynamics", "Stored note")

    def unavailable(_text):
        raise semantic.SemanticUnavailable("model offline")

    monkeypatch.setattr(semantic, "embed_text", unavailable)
    results = memory.relevant("knowledge", "entropy thermodynamics", limit=1)
    assert results[0]["prompt"] == "entropy in thermodynamics"


def test_forgetting_memory_also_removes_its_embedding(db, monkeypatch):
    monkeypatch.setattr(semantic, "enabled", lambda: True)
    monkeypatch.setattr(semantic, "embed_text", lambda _text: _vector(3))
    memory_id = memory.save("knowledge", "remember this note", "answer")
    assert memory.semantic_summary()["indexed_memories"] == 1

    assert memory.forget(memory_id) is True
    assert memory.semantic_summary()["indexed_memories"] == 0


def test_semantic_backfill_disabled_is_safe(db, monkeypatch):
    monkeypatch.setattr(semantic, "enabled", lambda: False)
    result = memory.backfill_semantic()
    assert result["enabled"] is False
    assert result["indexed"] == 0


def test_semantic_api_reports_status_and_backfills(db, monkeypatch):
    from starlette.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(semantic, "enabled", lambda: False)
    client = TestClient(app)
    status = client.get("/memory/semantic")
    assert status.status_code == 200
    assert status.json()["retrieval"] == "bm25-fallback"
    assert client.post("/memory/semantic/backfill?limit=0").status_code == 200
    assert client.post("/memory/semantic/backfill?limit=not-a-number").status_code == 422
