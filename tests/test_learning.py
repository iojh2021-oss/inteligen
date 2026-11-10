import json

from app import learning
from app.worlds import WORLDS


def state(status="complete", ok=None, scores=None):
    ok = list(WORLDS) if ok is None else ok
    return {"status": status, "successful_worlds": ok, "timestamp": "2026-01-01T00:00:00",
            "request_id": "r", "evaluation": {"worlds": scores or {}}}


def test_counters_stay_consistent_across_complete_partial_and_failed_cycles(db):
    learning.record_status(state())
    learning.record_status(state("partial", ok=["knowledge", "reasoning"]))
    learning.record_failed_cycle("model down")
    status = learning.load_status()
    assert status["cycles_total"] == 3
    assert (status["cycles_complete"], status["cycles_partial"], status["cycles_failed"]) == (1, 1, 1)
    for name in WORLDS:
        world = status["per_world"][name]
        assert world["ok"] + world["fail"] == world["runs"] == 3
    assert status["per_world"]["science"]["fail"] == 2
    assert status["per_world"]["knowledge"]["ok"] == 2
    assert status["last_error"] == "model down"


def test_each_world_keeps_its_own_scores_and_best(db):
    learning.record_status(state(scores={"science": {"score": 50, "missing": ["test"]}}))
    learning.record_status(state(scores={"science": {"score": 100, "missing": []}}))
    learning.record_status(state(scores={"science": {"score": 75, "missing": ["limitations"]}}))
    science = learning.load_status()["per_world"]["science"]
    assert (science["last_score"], science["best_score"]) == (75, 100)
    assert learning.load_status()["per_world"]["knowledge"]["last_score"] is None


def test_curriculum_rotates_and_wraps(db):
    topics = learning.load_curriculum()
    assert len(topics) >= 10 and len(set(topics)) == len(topics)
    assert learning.pick_topic(0) != learning.pick_topic(1)
    assert learning.pick_topic(len(topics)) == learning.pick_topic(0)


def test_curriculum_does_not_overlap_the_lab_benchmark():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "evolution"
    bench = {q["question"] for q in json.loads((root / "benchmark.json").read_text())["questions"]}
    topics = {t["question"] for t in json.loads((root / "curriculum.json").read_text())["topics"]}
    assert not bench & topics


def test_coaching_is_per_world_and_empty_when_nothing_repeats():
    history = [{"config_version": 1, "worlds": {
        "science": {"score": 50, "missing": ["hypothesis", "test"]},
        "knowledge": {"score": 100, "missing": []}}} for _ in range(3)]
    text = learning.coaching("science", history, 1)
    assert "hypothesis" in text and "test" in text
    assert learning.coaching("knowledge", history, 1) == ""
    assert learning.coaching("reasoning", history, 1) == ""
    assert learning.coaching("science", history, 2) == ""
