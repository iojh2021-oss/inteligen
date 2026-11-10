"""Central brain: deterministic decision layer on top of the five worlds.

The orchestrator runs the worlds and synthesizes an answer. This module decides how far that
answer can be trusted *structurally* and what should happen next. It uses only observable
signals (which worlds responded, rubric coverage). It never claims the answer is correct.
"""

LOW_BELOW = 50
HIGH_AT_LEAST = 75


def assess(expected_worlds: int, successful_worlds: list, evaluation: dict, errors: dict = None) -> dict:
    errors = errors or {}
    ok = len(successful_worlds)
    score = evaluation.get("overall_score") if evaluation else None
    reasons = []
    if ok < expected_worlds:
        reasons.append(f"{expected_worlds - ok} of {expected_worlds} worlds unavailable")
    weak = sorted(
        name for name, item in (evaluation or {}).get("worlds", {}).items()
        if item.get("score") is not None and item["score"] < LOW_BELOW
    )
    if weak:
        reasons.append("low coverage in: " + ", ".join(weak))

    if ok == 0 or score is None:
        level = "low"
    elif ok < expected_worlds or score < LOW_BELOW:
        level = "low"
    elif score < HIGH_AT_LEAST or weak:
        level = "medium"
    else:
        level = "high"
    missing = {name: item.get("missing", []) for name, item in (evaluation or {}).get("worlds", {}).items()
               if item.get("missing")}
    if missing:
        reasons.append("missing criteria: " + "; ".join(
            f"{name} ({', '.join(items)})" for name, items in sorted(missing.items())))
    if score is not None and score < HIGH_AT_LEAST and not weak and ok == expected_worlds:
        reasons.append(f"overall coverage {score} is below {HIGH_AT_LEAST}")
    if not reasons:
        reasons.append("all worlds answered and covered their rubric criteria")

    actions = {
        "low": "Human review required. Do not rely on this answer; rerun or inspect the failed or weak worlds.",
        "medium": "Review the missing criteria before using the answer.",
        "high": "Usable as a draft. Facts still need independent verification.",
    }
    return {
        "coverage_level": level,
        "overall_score": score,
        "worlds_ok": ok,
        "worlds_expected": expected_worlds,
        "weak_worlds": weak,
        "failed_worlds": sorted(errors),
        "reasons": reasons,
        "requires_human_review": level != "high",
        "next_action": actions[level],
        "scope": "structural coverage only; not a measure of truth or correctness",
    }
