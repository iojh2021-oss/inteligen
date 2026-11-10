"""Evaluation and evolution engine (proposal-only, human-approved).

Loop:
  1. Every production cycle appends its rubric result to evolution/history.json.
  2. The engine finds criteria that the current stable version keeps missing.
  3. It builds ONE candidate version by adding the matching instruction(s) from a fixed library
     (model output never becomes configuration).
  4. The simulation lab runs baseline and candidate on the fixed benchmark and compares paired
     scores. The verdict is recommended / inconclusive / rejected.
  5. A human reads the report and promotes (or ignores) it via the Evolution workflow.
     Rollback to any earlier version is available the same way.

Honest limit: the rubric counts structural coverage (keywords for each criterion). A candidate
can raise the score by making the model mention the criteria, so a "recommended" verdict means
"better rubric coverage on the benchmark", not "provably better answers". Read the excerpts.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app import config, learning, memory, simulation, state_guard, versions
from app.evaluation import RUBRIC_VERSION
from app.worlds import MAX_ADDITION_CHARS, WORLDS

HISTORY_LIMIT = 100
WINDOW = 5            # recent cycles (under the current stable version) that are considered
MIN_SHARE = 0.5       # a criterion must be missing in at least this share of them
MAX_NEW_PER_WORLD = 2
MIN_PAIRED = 4        # minimum paired (question, world) scores for any verdict but inconclusive
MIN_GAIN = 10.0       # mean points gained (0-100 scale) to recommend
MAX_WORLD_REGRESSION = -10.0
REJECT_BELOW = -5.0

INSTRUCTIONS = {
    "knowledge": {
        "concepts": "Define the key concepts explicitly before using them.",
        "fact_vs_assumption": "Label each claim as a verified fact, an inference, or an assumption.",
        "uncertainty": "State what remains uncertain and your confidence level.",
        "evidence_limits": "Name the evidence or source behind each claim and the limits of that evidence.",
    },
    "reasoning": {
        "ordered_steps": "Present numbered steps (first, second, third) in order.",
        "assumptions": "List the assumptions or premises explicitly.",
        "countercheck": "Give a counterexample or alternative explanation and test the conclusion against it.",
        "conclusion": "End with a clearly labeled conclusion.",
    },
    "science": {
        "hypothesis": "State a clear, testable hypothesis.",
        "prediction": "State the expected outcome (prediction) if the hypothesis is true.",
        "test": "Describe a safe experiment or test and how it would be measured.",
        "limitations": "State the limitations and risks of the test.",
    },
    "creativity": {
        "multiple_ideas": "Offer at least three distinct ideas or options.",
        "tradeoffs": "State the advantages and disadvantages (trade-offs) of each option.",
        "original_combination": "Include one idea that combines or reframes existing approaches.",
        "practicality": "Say how each idea could be implemented in a practical way.",
    },
    "learning": {
        "identified_gap": "Name the specific gap or weakness you found.",
        "measurable_metric": "Define a measurable metric or score for it.",
        "evaluation_test": "Describe an evaluation test or benchmark to check the improvement.",
        "improvement": "Propose one reversible improvement for the next iteration.",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dir() -> Path:
    return Path(config.evolution_dir())


# ---- history -----------------------------------------------------------------

def load_history() -> list:
    return learning.load_history()


def record_cycle(state: dict) -> dict:
    """Append one production cycle's rubric result to the committed history."""
    report = state.get("evaluation") or {}
    entry = {
        "timestamp": state.get("timestamp") or _now(),
        "request_id": state.get("request_id"),
        "config_version": state.get("config_version", 1),
        "model": state.get("model"),
        "overall_score": report.get("overall_score"),
        "worlds": {
            name: {"score": item.get("score"), "missing": item.get("missing", [])}
            for name, item in (report.get("worlds") or {}).items()
        },
    }
    history = (load_history() + [entry])[-HISTORY_LIMIT:]
    state_guard.atomic_write_json(_dir() / "history.json", history, indent=1)
    return entry


# ---- candidate derivation ------------------------------------------------------

def derive_candidate(history: list, stable: dict):
    """Return (candidate_additions, changes). changes is empty when there is nothing to improve."""
    recent = [h for h in history if h.get("config_version") == stable["version"]][-WINDOW:]
    additions = dict(stable["world_additions"])
    changes = []
    if not recent:
        return additions, changes
    for world in WORLDS:
        counts = {}
        seen = 0
        for entry in recent:
            item = (entry.get("worlds") or {}).get(world) or {}
            if item.get("score") is None:
                continue
            seen += 1
            for criterion in item.get("missing", []):
                counts[criterion] = counts.get(criterion, 0) + 1
        if not seen:
            continue
        weak = [c for c, n in counts.items()
                if n / seen >= MIN_SHARE and c in INSTRUCTIONS[world]]
        weak.sort(key=lambda c: (-counts[c], c))
        added = 0
        for criterion in weak:
            line = "- " + INSTRUCTIONS[world][criterion]
            current = additions.get(world, "")
            if line in current or added >= MAX_NEW_PER_WORLD:
                continue
            updated = (current + "\n" + line).strip()
            if len(updated) > MAX_ADDITION_CHARS:
                continue
            additions[world] = updated
            changes.append({"world": world, "criterion": criterion,
                            "instruction": INSTRUCTIONS[world][criterion],
                            "missed_in": f"{counts[criterion]}/{seen} recent cycles"})
            added += 1
    return additions, changes


# ---- comparison ----------------------------------------------------------------

def _mean(values):
    return round(sum(values) / len(values), 1) if values else None


def compare(baseline: dict, candidate: dict) -> dict:
    """Paired comparison of rubric scores. Unavailable worlds never count as zero."""
    if len(baseline["runs"]) != len(candidate["runs"]) or not baseline["runs"]:
        return {"verdict": "inconclusive", "reason": "baseline and candidate ran different numbers "
                "of benchmark runs", "paired_scores": 0, "baseline_mean": None,
                "candidate_mean": None, "mean_gain": None, "per_world_gain": {},
                "unavailable": {"baseline": 0, "candidate": 0}, "thresholds": {}}
    diffs, base_scores, cand_scores = [], [], []
    per_world = {w: [] for w in WORLDS}
    unavailable = {"baseline": 0, "candidate": 0}
    for b_run, c_run in zip(baseline["runs"], candidate["runs"]):
        for world in WORLDS:
            b, c = b_run["scores"][world], c_run["scores"][world]
            unavailable["baseline"] += b is None
            unavailable["candidate"] += c is None
            if b is None or c is None:
                continue
            base_scores.append(b)
            cand_scores.append(c)
            diffs.append(c - b)
            per_world[world].append(c - b)
    gain = _mean(diffs)
    world_gain = {w: _mean(v) for w, v in per_world.items()}
    regressions = [w for w, g in world_gain.items() if g is not None and g <= MAX_WORLD_REGRESSION]

    if len(diffs) < MIN_PAIRED:
        verdict, why = "inconclusive", f"only {len(diffs)} paired scores (need {MIN_PAIRED})"
    elif regressions:
        verdict, why = "rejected", "regression in: " + ", ".join(sorted(regressions))
    elif gain >= MIN_GAIN and unavailable["candidate"] <= unavailable["baseline"]:
        verdict, why = "recommended", f"mean gain {gain} points with no reliability loss"
    elif gain <= REJECT_BELOW:
        verdict, why = "rejected", f"mean change {gain} points"
    else:
        verdict, why = "inconclusive", f"mean change {gain} points is within the noise band"
    return {
        "verdict": verdict,
        "reason": why,
        "paired_scores": len(diffs),
        "baseline_mean": _mean(base_scores),
        "candidate_mean": _mean(cand_scores),
        "mean_gain": gain,
        "per_world_gain": world_gain,
        "unavailable": unavailable,
        "thresholds": {"min_gain": MIN_GAIN, "min_paired": MIN_PAIRED,
                       "max_world_regression": MAX_WORLD_REGRESSION},
    }


# ---- one full evaluation cycle ---------------------------------------------------

async def evaluate_cycle() -> dict:
    stable = versions.ensure_baseline()
    candidate_additions, changes = derive_candidate(load_history(), stable)
    if not changes:
        return {"status": "no_candidate",
                "message": "No recurring weakness found under the current stable version "
                           "(or no production cycle has run yet). Nothing to test."}
    questions = simulation.load_benchmark()
    repeats = config.lab_repeats()
    baseline = await simulation.run_benchmark(stable["world_additions"], questions, repeats)
    candidate = await simulation.run_benchmark(candidate_additions, questions, repeats)
    comparison = compare(baseline, candidate)
    proposal = {
        "id": datetime.now(timezone.utc).strftime("p-%Y%m%dT%H%M%S"),
        "created_at": _now(),
        "status": {"recommended": "recommended", "rejected": "rejected"}.get(
            comparison["verdict"], "inconclusive"),
        "base_version": stable["version"],
        "model": config.model_name(),
        "changes": changes,
        "candidate_additions": versions.clean_additions(candidate_additions),
        "benchmark_questions": questions,
        "rubric_version": RUBRIC_VERSION,
        "repeats": repeats,
        "conditions": {"model": config.model_name(), "memory": "disabled in lab",
                       "runs_per_version": len(baseline["runs"])},
        "baseline_runs": [{"scores": r["scores"], "errors": r["errors"]} for r in baseline["runs"]],
        "candidate_runs": [{"scores": r["scores"], "errors": r["errors"]} for r in candidate["runs"]],
        "comparison": comparison,
        "samples": [{"question": r["question"], "excerpts": r["excerpts"]} for r in candidate["runs"]],
        "caveat": "Rubric coverage only. Read the samples before approving.",
    }
    versions.save_proposal(proposal)
    summary = (f"Evolution proposal {proposal['id']} on v{stable['version']}: "
               f"{comparison['verdict']} ({comparison['reason']}). Changes: "
               + "; ".join(f"{c['world']}/{c['criterion']}" for c in changes))
    memory.save("learning", f"evolution experiment {proposal['id']}", summary, kind="experiment")
    memory.save("central", f"evolution decision {proposal['id']}",
                f"Verdict {comparison['verdict']}; promotion needs human approval.", kind="decision")
    return {"status": "proposal", "proposal": proposal}


# ---- dashboard export ---------------------------------------------------------------

def _summary(p: dict) -> dict:
    c = p.get("comparison") or {}
    return {"id": p["id"], "created_at": p.get("created_at"), "status": p.get("status"),
            "base_version": p.get("base_version"), "verdict": c.get("verdict"),
            "reason": c.get("reason"), "baseline_mean": c.get("baseline_mean"),
            "candidate_mean": c.get("candidate_mean"), "mean_gain": c.get("mean_gain"),
            "changes": [f"{x['world']}/{x['criterion']}" for x in p.get("changes", [])]}


def export_state(state_dir: str = "docs/state") -> None:
    folder = Path(state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stable = versions.load_stable()
    proposals = versions.list_proposals()
    payload = {
        "updated_at": _now(),
        "stable": stable,
        "versions": [{"version": v.get("version"), "created_at": v.get("created_at"),
                      "note": v.get("note"), "approved_by": v.get("approved_by")}
                     for v in versions.list_versions()],
        "proposals": [_summary(p) for p in proposals[-10:]],
        "latest_proposal": proposals[-1] if proposals else None,
        "benchmark_size": len(simulation.load_benchmark()) if (_dir() / "benchmark.json").exists() else 0,
    }
    state_guard.atomic_write_json(folder / "evolution.json", payload)
    state_guard.atomic_write_json(folder / "status.json", learning.load_status())
    history = [
        {"t": h.get("timestamp"), "v": h.get("config_version"), "score": h.get("overall_score")}
        for h in load_history()[-30:]
    ]
    state_guard.atomic_write_json(folder / "history.json", history, indent=1)
