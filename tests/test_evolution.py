import asyncio
import json

from app import evolution, memory, model, simulation, versions
from app.worlds import WORLDS

RICH = {
    "knowledge": "concept; verified fact and assumption; uncertainty; evidence and source limits",
    "reasoning": "step one first; assumption; counterexample; conclusion",
    "science": "hypothesis; prediction; experiment to measure; limitation",
    "creativity": "ideas; trade-offs; combine; practical",
    "learning": "gap; metric; evaluation test; improvement",
}


def run(coro):
    return asyncio.run(coro)


class GuidedModel:
    """Produces rubric-rich text only when the system prompt carries approved guidance."""

    def __init__(self, break_candidate=False):
        self.break_candidate = break_candidate

    async def generate(self, system_prompt, user_prompt):
        for name in WORLDS:
            if f"You are the {name.capitalize()} World" in system_prompt:
                if "Additional approved guidance" in system_prompt:
                    if self.break_candidate:
                        raise model.ModelUnavailable("candidate prompt broke the model")
                    return RICH[name]
                return "plain answer"
        return "synthesis"

    async def ping(self):
        return True


def weak_history(version=1, cycles=3):
    return [{"timestamp": f"2026-01-0{i + 1}", "config_version": version, "worlds": {
        "science": {"score": 50, "missing": ["hypothesis", "prediction"]},
        "knowledge": {"score": 100, "missing": []},
    }} for i in range(cycles)]


def test_candidate_targets_recurring_weaknesses_from_the_fixed_library(db):
    additions, changes = evolution.derive_candidate(weak_history(), versions.ensure_baseline())
    assert {(c["world"], c["criterion"]) for c in changes} == {
        ("science", "hypothesis"), ("science", "prediction")}
    assert "testable hypothesis" in additions["science"]
    assert "knowledge" not in additions


def test_no_candidate_without_recurring_weakness_or_history(db):
    stable = versions.ensure_baseline()
    assert evolution.derive_candidate([], stable)[1] == []
    assert evolution.derive_candidate(weak_history(version=7), stable)[1] == []
    once = weak_history(cycles=3)
    once[1]["worlds"]["science"]["missing"] = []
    once[2]["worlds"]["science"]["missing"] = []
    assert evolution.derive_candidate(once, stable)[1] == []


def test_existing_guidance_is_not_duplicated(db):
    stable = versions.ensure_baseline()
    additions, _ = evolution.derive_candidate(weak_history(), stable)
    stable["world_additions"] = additions
    again, changes = evolution.derive_candidate(weak_history(), stable)
    assert changes == [] and again == additions


def lab(scores):
    return {"runs": [{"scores": s, "errors": {}} for s in scores]}


def scores(value):
    return {w: value for w in WORLDS}


def test_compare_recommends_clear_gain_rejects_regression_and_needs_enough_data():
    assert evolution.compare(lab([scores(50)] * 2), lab([scores(75)] * 2))["verdict"] == "recommended"
    assert evolution.compare(lab([scores(75)] * 2), lab([scores(50)] * 2))["verdict"] == "rejected"
    assert evolution.compare(lab([scores(50)] * 2), lab([scores(50)] * 2))["verdict"] == "inconclusive"
    assert evolution.compare(lab([scores(50)]), lab([scores(100)]))["verdict"] == "recommended"
    tiny = {"runs": [{"scores": dict(scores(None), science=50), "errors": {}}]}
    assert evolution.compare(tiny, tiny)["verdict"] == "inconclusive"


def test_unavailable_worlds_are_not_counted_as_zero_and_block_recommendation():
    broken = dict(scores(100), science=None)
    result = evolution.compare(lab([scores(50)] * 2), lab([broken] * 2))
    assert result["paired_scores"] == 8 and result["unavailable"]["candidate"] == 2
    assert result["verdict"] != "recommended"


def prepare(db, monkeypatch):
    evo = db / "evolution"
    evo.mkdir(exist_ok=True)
    (evo / "benchmark.json").write_text(json.dumps({"questions": [
        {"id": "b1", "question": "How can a town save water?"},
        {"id": "b2", "question": "Why do students forget lessons?"}]}))
    versions.ensure_baseline()
    (evo / "history.json").write_text(json.dumps(weak_history()))


def test_full_cycle_proposes_a_recommended_candidate_without_touching_production(db, monkeypatch):
    prepare(db, monkeypatch)
    original = model.get_client()
    model.set_client(GuidedModel())
    try:
        result = run(evolution.evaluate_cycle())
    finally:
        model.set_client(original)
    proposal = result["proposal"]
    assert result["status"] == "proposal" and proposal["status"] == "recommended"
    assert proposal["comparison"]["mean_gain"] > 0 and proposal["samples"]
    # Lab isolation: no world memories or metrics from the lab runs.
    assert memory.stats()["by_kind"] == {"experiment": 1, "decision": 1}
    assert memory.metrics_summary() == {}
    # The stable version is unchanged until a human promotes.
    assert versions.load_stable()["version"] == 1
    new = versions.promote(proposal["id"], "alice")
    assert new["version"] == 2 and "testable hypothesis" in new["world_additions"]["science"]


def test_broken_candidate_is_not_recommended(db, monkeypatch):
    prepare(db, monkeypatch)
    original = model.get_client()
    model.set_client(GuidedModel(break_candidate=True))
    try:
        result = run(evolution.evaluate_cycle())
    finally:
        model.set_client(original)
    assert result["proposal"]["status"] != "recommended"


def test_export_state_writes_dashboard_files(db, monkeypatch, tmp_path):
    prepare(db, monkeypatch)
    out = tmp_path / "state"
    evolution.export_state(str(out))
    data = json.loads((out / "evolution.json").read_text())
    assert data["stable"]["version"] == 1 and data["versions"][0]["version"] == 1
    assert json.loads((out / "history.json").read_text())[0]["v"] == 1


def test_record_cycle_appends_history(db):
    evolution.record_cycle({"request_id": "r1", "config_version": 2, "evaluation": {
        "overall_score": 80, "worlds": {"science": {"score": 50, "missing": ["test"]}}}})
    entry = evolution.load_history()[-1]
    assert entry["config_version"] == 2 and entry["worlds"]["science"]["missing"] == ["test"]
