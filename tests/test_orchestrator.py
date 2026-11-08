import asyncio

import pytest

from app import memory, model
from app.orchestrator import run_five_worlds


def run(coro):
    return asyncio.run(coro)


def test_one_request_reaches_all_five_worlds_and_is_synthesized(fake):
    result = run(run_five_worlds("what is entropy"))
    assert result["answer"] == "final-synthesis"
    assert set(result["worlds"]) == {"knowledge", "reasoning", "science", "creativity", "learning"}
    assert result["errors"] == {}
    assert len(fake.calls) == 6  # five worlds + central synthesis


def test_learning_world_receives_the_other_worlds_outputs(fake):
    run(run_five_worlds("what is entropy"))
    learning_prompt = next(u for s, u in fake.calls if "Learning World" in s)
    for name in ("knowledge", "reasoning", "science", "creativity"):
        assert f"answer-from-{name}" in learning_prompt


def test_one_failing_world_does_not_kill_the_request(fake):
    fake.fail_worlds = {"science"}
    result = run(run_five_worlds("what is entropy"))
    assert "science" in result["errors"]
    assert result["worlds"]["science"].startswith("(unavailable")
    assert result["answer"] == "final-synthesis"
    learning_prompt = next(u for s, u in fake.calls if "Learning World" in s)
    assert "SCIENCE WORLD: unavailable" in learning_prompt


def test_all_worlds_failing_raises(fake):
    fake.fail_worlds = {"knowledge", "reasoning", "science", "creativity", "learning"}
    with pytest.raises(model.ModelUnavailable):
        run(run_five_worlds("what is entropy"))


def test_memory_persists_with_provenance(fake):
    result = run(run_five_worlds("what is entropy"))
    items = memory.recent(20)
    assert {i["world"] for i in items} == {
        "knowledge", "reasoning", "science", "creativity", "learning", "central"}
    assert all(i["request_id"] == result["request_id"] for i in items)
    assert all(i["created_at"] for i in items)


def test_relevant_retrieval_is_per_world_and_supports_persian(db):
    memory.save("knowledge", "entropy and heat", "entropy measures disorder")
    memory.save("knowledge", "cooking pasta", "boil water")
    memory.save("reasoning", "entropy puzzle", "other world's note")
    memory.save("knowledge", "قطب‌نما چگونه کار می‌کند", "جهت شمال مغناطیسی")
    hits = memory.relevant("knowledge", "tell me about entropy")
    assert [h["result"] for h in hits] == ["entropy measures disorder"]
    assert memory.relevant("knowledge", "قطب‌نما") != []
    assert memory.relevant("knowledge", "zzzz unrelated") == []


def test_forget_removes_a_memory(db):
    memory.save("knowledge", "p", "r")
    item = memory.recent(1)[0]
    assert memory.forget(item["id"]) is True
    assert memory.recent(5) == []
    assert memory.forget(item["id"]) is False


def test_metrics_are_recorded_per_world(fake):
    fake.fail_worlds = {"creativity"}
    run(run_five_worlds("q one"))
    run(run_five_worlds("q two"))
    summary = memory.metrics_summary()
    assert summary["knowledge"]["runs"] == 2
    assert summary["knowledge"]["success_rate"] == 1.0
    assert summary["creativity"]["success_rate"] == 0.0


def test_old_database_is_migrated(db):
    import sqlite3
    path = db / "memory.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE memories (id INTEGER PRIMARY KEY AUTOINCREMENT,
        world TEXT NOT NULL, prompt TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL)""")
    conn.execute("INSERT INTO memories(world,prompt,result,created_at) VALUES('knowledge','p','r','2026-01-01')")
    conn.commit()
    conn.close()
    items = memory.recent(5)
    assert items[0]["result"] == "r" and items[0]["request_id"] is None
