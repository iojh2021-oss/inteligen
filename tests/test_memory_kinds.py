import sqlite3

from app import memory


def test_kinds_are_stored_and_failures_are_not_retrieved_as_knowledge(db):
    memory.save("knowledge", "entropy question", "entropy is disorder")
    memory.save("knowledge", "entropy question", "Failed: model down", kind="failure")
    memory.save("learning", "evolution experiment p-1", "verdict recommended", kind="experiment")
    hits = memory.relevant("knowledge", "entropy question")
    assert [h["result"] for h in hits] == ["entropy is disorder"]
    assert memory.latest_of_kind("experiment", 2)[0]["kind"] == "experiment"


def test_unknown_kind_is_rejected(db):
    try:
        memory.save("knowledge", "p", "r", kind="gossip")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_stats_count_by_world_and_kind(db):
    memory.save("knowledge", "a", "b")
    memory.save("learning", "c", "d", kind="experiment")
    stats = memory.stats()
    assert stats["total"] == 2
    assert stats["by_world"] == {"knowledge": 1, "learning": 1}
    assert stats["by_kind"] == {"experience": 1, "experiment": 1}


def test_old_database_without_kind_is_migrated(db):
    conn = sqlite3.connect(db / "memory.sqlite3")
    conn.execute("""CREATE TABLE memories (id INTEGER PRIMARY KEY AUTOINCREMENT,
        world TEXT NOT NULL, prompt TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL,
        request_id TEXT)""")
    conn.execute("INSERT INTO memories(world,prompt,result,created_at) VALUES('knowledge','p','r','2026-01-01')")
    conn.commit()
    conn.close()
    assert memory.recent(5)[0]["kind"] == "experience"
