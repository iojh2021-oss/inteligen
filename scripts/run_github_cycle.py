"""Run Inteligen on a temporary GitHub-hosted runner using local Ollama."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPOSITORY_ROOT)
sys.path.insert(0, str(REPOSITORY_ROOT))

from app import evaluation, memory, model, safety
from app.orchestrator import run_five_worlds
from app.worlds import WORLDS

def main() -> None:
    question = os.environ.get("BRAIN_QUESTION", "").strip()
    if not 2 <= len(question) <= 6000:
        raise SystemExit("BRAIN_QUESTION must contain 2 to 6000 characters.")
    if not safety.screen_text(question)["allowed"]:
        raise SystemExit("BRAIN_QUESTION was rejected by the safety gate.")
    if not asyncio.run(model.get_client().ping()):
        raise SystemExit("The local Ollama OpenAI-compatible endpoint is not reachable.")

    result = asyncio.run(run_five_worlds(question))
    timestamp = datetime.now(timezone.utc).isoformat()
    successful_worlds = [name for name, value in result["worlds"].items()
                         if not str(value).startswith("(unavailable:")]
    expected_worlds = list(WORLDS)
    missing_worlds = sorted(set(expected_worlds) - set(result["worlds"]))
    if missing_worlds:
        raise SystemExit("Runner returned an incomplete world set: " + ", ".join(missing_worlds))

    evaluation_report = evaluation.evaluate_worlds(result["worlds"])
    state = {
        "schema_version": 3,
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
        "safety": result["safety"],
        "errors": result["errors"],
    }

    state_dir = Path("docs/state")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "latest.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (state_dir / "evaluation.json").write_text(
        json.dumps(evaluation_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = {
        "updated_at": timestamp,
        "worlds": memory.metrics_summary(),
        "memory_items": len(memory.recent(100)),
        "evaluation": {
            "rubric_version": evaluation_report["rubric_version"],
            "overall_score": evaluation_report["overall_score"],
            "evaluated_worlds": evaluation_report["evaluated_worlds"],
            "scope": evaluation_report["scope"],
        },
        "safety": {
            "guardrail_version": result["safety"]["guardrail_version"],
            "blocked_outputs": result["safety"]["blocked_outputs"],
            "scope": result["safety"]["scope"],
        },
        "architecture": "central-brain + five-worlds + sqlite-memory + evaluation + safety-gate",
    }
    (state_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True, "request_id": result["request_id"], "status": state["status"],
        "successful_worlds": successful_worlds, "expected_worlds": expected_worlds,
        "evaluation_overall_score": evaluation_report["overall_score"],
        "evaluation_scope": evaluation_report["scope"], "safety": result["safety"],
        "failed_worlds": result["errors"],
        "memory_path": os.environ.get("DATABASE_PATH", "data/memory.sqlite3"),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
