import json
from pathlib import Path

from app.evaluation import evaluate_results, score_output
from app.worlds import WORLDS


def test_score_is_deterministic_and_explains_rubric_matches():
    first = score_output(
        "Evidence and verified facts support this conclusion. The hypothesis predicts "
        "an experiment with a control and a measurable result.",
        [["evidence", "source"], ["hypothesis"], ["experiment"], ["control"]],
        min_words=10,
    )
    second = score_output(
        "Evidence and verified facts support this conclusion. The hypothesis predicts "
        "an experiment with a control and a measurable result.",
        [["evidence", "source"], ["hypothesis"], ["experiment"], ["control"]],
        min_words=10,
    )
    assert first == second
    assert first["score"] == 100
    assert first["passed"] is True


def test_empty_and_unavailable_outputs_do_not_pass():
    assert score_output("", [["evidence"]])["passed"] is False
    assert score_output("(unavailable: timeout)", [["evidence"]])["score"] == 0


def test_missing_world_marks_evaluation_incomplete():
    cases = json.loads(
        (Path(__file__).parent / "fixtures" / "benchmark_cases.json").read_text(encoding="utf-8")
    )
    results = [{"case_id": cases[0]["id"], "worlds": {"knowledge": "some evidence"}}]
    report = evaluate_results(results, cases[:1])
    assert report["status"] == "incomplete"
    assert set(report["per_world"]) == set(WORLDS)


def test_complete_benchmark_reports_all_worlds_and_limitations():
    cases = json.loads(
        (Path(__file__).parent / "fixtures" / "benchmark_cases.json").read_text(encoding="utf-8")
    )
    outputs = {}
    for name in WORLDS:
        outputs[name] = (
            "Evidence and verified facts, source, data and uncertainty. "
            "Assumption, steps, logic, counterexample and conclusion. "
            "Hypothesis, prediction, experiment, test, control and limitation. "
            "Alternative, approach, idea, trade-off and novel option. "
            "Metric, measure, baseline, comparison, regression, improvement and iteration."
        )
    results = [{"case_id": case["id"], "worlds": outputs} for case in cases]
    report = evaluate_results(results, cases)
    assert report["status"] == "complete"
    assert report["aggregate_mean_score"] > 0
    assert "factual correctness" in " ".join(report["limitations"])
