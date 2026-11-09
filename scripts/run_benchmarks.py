"""Run the fixed, reproducible five-world evaluation suite against the configured model."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app import model
from app.evaluation import evaluate_results
from app.orchestrator import run_five_worlds


def main():
    cases = json.loads(Path("tests/fixtures/benchmark_cases.json").read_text(encoding="utf-8"))
    if not asyncio.run(model.get_client().ping()):
        raise SystemExit("Configured model endpoint is not reachable.")

    results = []
    for case in cases:
        result = asyncio.run(run_five_worlds(case["prompt"]))
        results.append({"case_id": case["id"], "worlds": result["worlds"]})

    report = evaluate_results(results, cases)
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    report["model"] = os.environ.get("MODEL_NAME", "configured-model")
    report["execution"] = "github-hosted-runner"
    Path("evaluation-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "aggregate_mean_score": report["aggregate_mean_score"],
        "per_world": report["per_world"],
        "report_file": "evaluation-report.json",
        "note": "Rubric proxy only; not a semantic correctness score.",
    }, ensure_ascii=False))
    if report["status"] != "complete":
        raise SystemExit("Evaluation output is incomplete.")


if __name__ == "__main__":
    main()
