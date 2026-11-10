"""Run one bounded Inteligen learning cycle on a temporary GitHub-hosted runner.

Each cycle: restore/verify state -> pick a task (curriculum or manual question) -> five worlds
-> central synthesis -> evaluation -> counters, history and dashboard files -> validation ->
backup. The workflow then pushes the state to the `state` branch. Nothing here loops or
schedules itself; the GitHub Actions cron decides when the next cycle starts.
The repository is public: never submit secrets or private information.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPOSITORY_ROOT)
sys.path.insert(0, str(REPOSITORY_ROOT))

from app import brain, evaluation, evolution, learning, memory, model, state_guard, versions  # noqa: E402
from app.orchestrator import run_five_worlds  # noqa: E402
from app.worlds import WORLDS  # noqa: E402


def fail_cycle(reason: str) -> None:
    learning.record_failed_cycle(reason)
    versions.ensure_baseline()
    evolution.export_state()
    raise SystemExit(reason)


def main() -> None:
    notice = state_guard.recover_if_needed()
    if notice:
        print("STATE RECOVERY:", notice)
    problems = state_guard.validate_state()
    if problems:
        raise SystemExit("State is inconsistent, refusing to run: " + "; ".join(problems))

    status = learning.load_status()
    question = os.environ.get("BRAIN_QUESTION", "").strip()
    task_source = "manual"
    if not question or question.lower() == "auto":
        question = learning.pick_topic(status["cycles_total"])
        task_source = "curriculum"
    if not 2 <= len(question) <= 6000:
        raise SystemExit("The question must contain 2 to 6000 characters.")

    if not asyncio.run(model.get_client().ping()):
        fail_cycle("The local Ollama OpenAI-compatible endpoint is not reachable.")
    try:
        result = asyncio.run(run_five_worlds(question))
    except Exception as exc:  # every world failed, or an unexpected error
        fail_cycle(f"Cycle failed: {exc}")

    timestamp = datetime.now(timezone.utc).isoformat()
    successful_worlds = [
        name for name, value in result["worlds"].items()
        if not str(value).startswith("(unavailable:")
    ]
    expected_worlds = list(WORLDS)
    missing_worlds = sorted(set(expected_worlds) - set(result["worlds"]))
    if missing_worlds:
        fail_cycle("Runner returned an incomplete world set: " + ", ".join(missing_worlds))

    evaluation_report = evaluation.evaluate_worlds(result["worlds"])
    assessment = brain.assess(len(expected_worlds), successful_worlds, evaluation_report, result["errors"])
    state = {
        "schema_version": 4,
        "cycle_number": status["cycles_total"] + 1,
        "task_source": task_source,
        "config_version": result.get("config_version", versions.load_stable()["version"]),
        "status": "complete" if not result["errors"] and len(successful_worlds) == len(expected_worlds) else "partial",
        "expected_world_count": len(expected_worlds),
        "successful_worlds": successful_worlds,
        "timestamp": timestamp,
        "request_id": result["request_id"],
        "model": os.environ.get("MODEL_NAME", "qwen3:1.7b"),
        "execution": "github-hosted-runner",
        "question": question,
        "answer": result["answer"],
        "worlds": result["worlds"],
        "evaluation": evaluation_report,
        "central_assessment": assessment,
        "errors": result["errors"],
    }

    state_dir = Path("docs/state")
    state_guard.atomic_write_json(state_dir / "latest.json", state)
    state_guard.atomic_write_json(state_dir / "evaluation.json", evaluation_report)
    evolution.record_cycle(state)
    learning.record_status(state)
    memory.prune()
    metrics = {
        "updated_at": timestamp,
        "worlds": memory.metrics_summary(),
        "memory_items": memory.stats()["total"],
        "memory": memory.stats(),
        "config_version": state["config_version"],
        "evaluation": {
            "rubric_version": evaluation_report["rubric_version"],
            "overall_score": evaluation_report["overall_score"],
            "evaluated_worlds": evaluation_report["evaluated_worlds"],
            "scope": evaluation_report["scope"],
        },
        "architecture": "central-brain + five-worlds + long-term-memory + simulation-lab + evaluation-evolution",
    }
    state_guard.atomic_write_json(state_dir / "metrics.json", metrics)
    versions.ensure_baseline()
    evolution.export_state()

    problems = state_guard.validate_state()
    if problems:
        raise SystemExit("Refusing to save inconsistent state: " + "; ".join(problems))
    state_guard.backup_memory()
    print(json.dumps({
        "ok": True,
        "cycle_number": state["cycle_number"],
        "task_source": task_source,
        "request_id": result["request_id"],
        "status": state["status"],
        "successful_worlds": successful_worlds,
        "expected_worlds": expected_worlds,
        "evaluation_overall_score": evaluation_report["overall_score"],
        "evaluation_scope": evaluation_report["scope"],
        "failed_worlds": result["errors"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
