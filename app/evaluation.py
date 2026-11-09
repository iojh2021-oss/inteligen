"""Deterministic, explainable evaluation and baseline comparison for Inteligen.

This measures observable rubric coverage and response completeness. It is NOT a
semantic truth judge, safety certification, or proof of general intelligence.
"""
import re
from statistics import mean

from app.worlds import WORLDS

SCHEMA_VERSION = 2
PASS_THRESHOLD = 70


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", str(text).casefold(), flags=re.UNICODE)


def score_output(output: str, anchor_groups: list, min_words: int = 35) -> dict:
    text = str(output or "").strip()
    words = _words(text)
    usable = bool(text) and not text.startswith("(unavailable:")
    completeness = 20 if usable else 0
    length_score = 0
    if usable and min_words > 0:
        length_score = round(20 * min(len(words) / min_words, 1), 2)

    normalized = " ".join(words)
    matched = []
    for alternatives in anchor_groups:
        hits = [term for term in alternatives
                if re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", normalized)]
        matched.append({"matched": bool(hits), "terms": hits})

    coverage = (sum(item["matched"] for item in matched) / len(matched)) if matched else 1.0
    anchor_score = round(60 * coverage, 2)
    score = round(completeness + length_score + anchor_score, 2)
    return {
        "score": score,
        "usable": usable,
        "passed": usable and score >= PASS_THRESHOLD,
        "word_count": len(words),
        "components": {
            "response_present": completeness,
            "minimum_content": length_score,
            "rubric_coverage": anchor_score,
        },
        "rubric": matched,
    }


def evaluate_results(results: list[dict], benchmark_cases: list[dict]) -> dict:
    """Evaluate per-case world outputs and aggregate scores without model judging."""
    case_reports = []
    world_scores = {name: [] for name in WORLDS}
    for case in benchmark_cases:
        result = next((item for item in results if item.get("case_id") == case["id"]), None)
        outputs = (result or {}).get("worlds", {})
        world_reports = {}
        for name in WORLDS:
            criteria = case["worlds"][name]
            report = score_output(outputs.get(name, ""), criteria, case.get("min_words", 35))
            world_reports[name] = report
            world_scores[name].append(report["score"])
        case_complete = all(world_reports[name]["usable"] for name in WORLDS)
        case_reports.append({
            "case_id": case["id"],
            "complete": case_complete,
            "worlds": world_reports,
        })

    per_world = {
        name: {
            "mean_score": round(mean(scores), 2) if scores else 0,
            "cases_passed": sum(case["worlds"][name]["passed"] for case in case_reports),
            "cases_total": len(case_reports),
        }
        for name, scores in world_scores.items()
    }
    all_scores = [v["mean_score"] for v in per_world.values()]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete" if case_reports and all(c["complete"] for c in case_reports) else "incomplete",
        "all_cases_passed": bool(case_reports) and all(
            all(world["passed"] for world in case["worlds"].values())
            for case in case_reports
        ),
        "threshold": PASS_THRESHOLD,
        "aggregate_mean_score": round(mean(all_scores), 2) if all_scores else 0,
        "per_world": per_world,
        "cases": case_reports,
        "limitations": [
            "Scores measure response presence, minimum length, and explicit rubric-term coverage only.",
            "They do not verify factual correctness, semantic reasoning quality, or safety.",
            "A higher score is not permission to deploy or promote a candidate.",
        ],
    }


def compare_reports(baseline: dict, candidate: dict, max_regression: float = 0.0) -> dict:
    """Compare matching complete reports; this only advises and never promotes code."""
    if max_regression < 0:
        raise ValueError("max_regression must be non-negative")

    reasons = []
    if baseline.get("status") != "complete":
        reasons.append("baseline_incomplete")
    if candidate.get("status") != "complete":
        reasons.append("candidate_incomplete")

    baseline_cases = {case.get("case_id") for case in baseline.get("cases", [])}
    candidate_cases = {case.get("case_id") for case in candidate.get("cases", [])}
    if not baseline_cases or baseline_cases != candidate_cases:
        reasons.append("benchmark_cases_mismatch")

    base_worlds = baseline.get("per_world", {})
    candidate_worlds = candidate.get("per_world", {})
    world_deltas = {}
    for world in WORLDS:
        if world not in base_worlds or world not in candidate_worlds:
            reasons.append(f"missing_world:{world}")
            continue
        before = float(base_worlds[world].get("mean_score", 0))
        after = float(candidate_worlds[world].get("mean_score", 0))
        world_deltas[world] = round(after - before, 2)

    overall_delta = round(
        float(candidate.get("aggregate_mean_score", 0))
        - float(baseline.get("aggregate_mean_score", 0)), 2
    )
    regressions = {
        world: delta for world, delta in world_deltas.items()
        if delta < -max_regression
    }
    if regressions:
        reasons.append("world_regression")

    comparable = not any(
        reason in {"baseline_incomplete", "candidate_incomplete", "benchmark_cases_mismatch"}
        or reason.startswith("missing_world:")
        for reason in reasons
    )
    return {
        "schema_version": 1,
        "status": "comparable" if comparable else "not_comparable",
        "recommendation": "review_candidate" if comparable and not regressions else "reject_candidate",
        "baseline_score": baseline.get("aggregate_mean_score", 0),
        "candidate_score": candidate.get("aggregate_mean_score", 0),
        "overall_delta": overall_delta,
        "per_world_delta": world_deltas,
        "regressions": regressions,
        "max_allowed_regression": max_regression,
        "reasons": reasons,
        "promotion_allowed": False,
        "limitations": [
            "This comparison uses the same reported rubric scores; it is not a semantic quality judge.",
            "A review recommendation is not approval to merge, deploy, or promote a candidate.",
            "Comparable reports must use identical benchmark case IDs; model and runtime settings should also be recorded and reviewed.",
        ],
    }
