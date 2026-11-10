from app import brain, evaluation

GOOD = {
    "knowledge": "Concepts, verified facts, uncertainty and evidence sources.",
    "reasoning": "Step one, assumptions, an alternative, and a conclusion.",
    "science": "Hypothesis, prediction, experiment and limitation.",
    "creativity": "Several ideas with trade-offs, combine them, practical.",
    "learning": "Gap, metric, evaluation test, improvement.",
}


def test_high_level_needs_all_worlds_and_good_coverage():
    report = evaluation.evaluate_worlds(GOOD)
    result = brain.assess(5, list(GOOD), report, {})
    assert result["coverage_level"] == "high" and result["requires_human_review"] is False


def test_missing_world_forces_low_level_and_human_review():
    outputs = dict(GOOD, science="(unavailable: down)")
    report = evaluation.evaluate_worlds(outputs)
    result = brain.assess(5, [w for w in GOOD if w != "science"], report, {"science": "down"})
    assert result["coverage_level"] == "low"
    assert result["failed_worlds"] == ["science"] and result["requires_human_review"] is True


def test_weak_coverage_is_reported_and_never_claims_correctness():
    outputs = dict(GOOD, reasoning="Nothing useful.")
    report = evaluation.evaluate_worlds(outputs)
    result = brain.assess(5, list(GOOD), report, {})
    assert "reasoning" in result["weak_worlds"] and result["coverage_level"] == "medium"
    assert "not a measure of truth" in result["scope"]


def test_reasons_never_claim_full_coverage_when_criteria_are_missing():
    outputs = dict(GOOD, science="Hypothesis only.", creativity="Several ideas only.")
    report = evaluation.evaluate_worlds(outputs)
    result = brain.assess(5, list(GOOD), report, {})
    text = " ".join(result["reasons"])
    assert "covered their rubric criteria" not in text
    assert "science (" in text and "creativity (" in text and "prediction" in text
    assert result["coverage_level"] != "high"
