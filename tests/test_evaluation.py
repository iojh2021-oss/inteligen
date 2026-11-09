from app.evaluation import evaluate_text, evaluate_worlds


def test_world_rubric_returns_transparent_checks():
    result = evaluate_text(
        "science",
        "Hypothesis: X. Prediction: Y. Run a safe experiment and measure it. Limitation: small sample.",
    )
    assert result["score"] == 100
    assert result["passed"] == result["total"]
    assert result["missing"] == []
    assert "not truth" in result["interpretation"]


def test_missing_criteria_are_reported():
    result = evaluate_text("reasoning", "This is a conclusion.")
    assert result["score"] < 100
    assert "ordered_steps" in result["missing"]
    assert result["checks"]["conclusion"] is True


def test_unavailable_world_is_not_given_a_zero_quality_score():
    result = evaluate_worlds({
        "knowledge": "Concepts and verified facts with evidence and uncertainty.",
        "reasoning": "(unavailable: model down)",
        "science": "Hypothesis, prediction, experiment, limitation.",
        "creativity": "Several ideas, trade-offs, combine and practical approach.",
        "learning": "Gap, measurable metric, evaluation test and improvement.",
    })
    assert result["worlds"]["reasoning"]["status"] == "unavailable"
    assert result["worlds"]["reasoning"]["score"] is None
    assert result["evaluated_worlds"] == 4
