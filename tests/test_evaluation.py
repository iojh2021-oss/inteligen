import json
from pathlib import Path

from app.evaluation import evaluate_results, score_output
from app.worlds import WORLDS


def _cases():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "benchmark_cases.json").read_text(encoding="utf-8")
    )


def _usable_world_outputs():
    return {
        name: (
            "Evidence and verified facts, source, data and uncertainty. "
            "Assumption, steps, logic, counterexample and conclusion. "
            "Hypothesis, prediction, experiment, test, control and limitation. "
            "Alternative, approach, idea, trade-off and novel option. "
            "Metric, measure, baseline, comparison, regression, improvement and iteration."
        )
        for name in WORLDS
    }


def test_score_is_deterministic_and_explains_rubric_matches():
    text = (
        "Evidence and verified facts support this conclusion. The hypothesis predicts "
        "an experiment with a control and a measurable result."
    )
    first = score_output(text, [["evidence", "source"], ["hypothesis"], ["experiment"], ["control"]], min_words=10)
    second = score_output(text, [["evidence", "source"], ["hypothesis"], ["experiment"], ["control"]], min_words=10)
    assert first == second
    assert first["score"] == 100
    assert first["passed"] is True


def test_phrase_anchor_matches_after_normalization():
    report = score_output(
        "A careful trade-off and held-out evaluation improves reliability.",
        [["trade-off"], ["held-out"]],
        min_words=1,
    )
    assert all(item["matched"] for item in report["rubric"])


def test_empty_and_unavailable_outputs_do_not_pass():
    assert score_output("", [["evidence"]])["passed"] is False
    assert score_output("(unavailable: timeout)", [["evidence"]])["score"] == 0


def test_missing_world_marks_evaluation_incomplete():
    cases = _cases()
    results = [{"case_id": cases[0]["id"], "worlds": {"knowledge": "some evidence"}}]
    report = evaluate_results(results, cases[:1])
    assert report["status"] == "incomplete"
    assert set(report["per_world"]) == set(WORLDS)


def test_unavailable_world_marks_evaluation_incomplete_even_when_key_exists():
    cases = _cases()
    outputs = _usable_world_outputs()
    outputs["science"] = "(unavailable: model timeout)"
    report = evaluate_results([{"case_id": cases[0]["id"], "worlds": outputs}], cases[:1])
    assert report["status"] == "incomplete"
    assert report["cases"][0]["complete"] is False
    assert report["cases"][0]["worlds"]["science"]["usable"] is False


def test_complete_benchmark_reports_all_worlds_and_limitations():
    cases = _cases()
    results = [{"case_id": case["id"], "worlds": _usable_world_outputs()} for case in cases]
    report = evaluate_results(results, cases)
    assert report["status"] == "complete"
    assert report["aggregate_mean_score"] > 0
    assert "factual correctness" in " ".join(report["limitations"])
