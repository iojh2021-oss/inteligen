import asyncio

import pytest

from app.evaluation import compare_candidate, experiment_history, score_response


def run(coro):
    return asyncio.run(coro)


def test_score_response_is_explainable_and_bounded():
    report = score_response(
        "science",
        "A hypothesis predicts an outcome because one variable changes. "
        "Control the others; limitations remain uncertain.",
    )
    assert 0 <= report["score"] <= 100
    assert report["checks"]["world_relevance"] is True
    assert set(report["checks"]) == {
        "non_empty", "substantive_length", "world_relevance",
        "reasoning_signal", "limitation_or_uncertainty",
    }


def test_candidate_comparison_runs_all_worlds_and_persists_without_promotion(fake):
    report = run(compare_candidate("Use concise headings and state limitations."))
    assert set(report["worlds"]) == {"knowledge", "reasoning", "science", "creativity", "learning"}
    assert report["promotion"] == "not_performed"
    assert report["decision"] in {"candidate_better", "baseline_better", "no_measured_improvement"}
    assert len(fake.calls) == 10
    history = experiment_history(5)
    assert len(history) == 1
    assert history[0]["experiment_id"] == report["experiment_id"]


def test_candidate_length_is_limited():
    with pytest.raises(ValueError):
        run(compare_candidate("x" * 1201))
