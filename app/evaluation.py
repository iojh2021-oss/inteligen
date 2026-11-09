"""Deterministic, explainable evaluation for the five Inteligen worlds.

This measures observable rubric coverage and response completeness. It is NOT a
semantic truth judge, safety certification, or proof of general intelligence.
"""
import re
from statistics import mean

from app.worlds import WORLDS

SCHEMA_VERSION = 2
PASS_THRESHOLD = 70


def _words(text: str) -> list[str]:
    return re.findall(r"\\b[\\w'-]+\\b", str(text).casefold(), flags=re.UNICODE)


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
                if re.search(r"(?<!\\w)" + re.escape(term.casefold()) + r"(?!\\w)", normalized)]
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
            "cases_passed": sum(
                case["worlds"][name]["passed"] for case in case_reports
            ),
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
