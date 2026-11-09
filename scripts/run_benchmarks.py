"""Run isolated, reproducible five-world evaluations against the configured model."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app import model
from app.evaluation import evaluate_results
from app.orchestrator import run_five_worlds


async def run_cases(cases: list[dict], database_dir: Path) -> list[dict]:
    results = []
    original_db = os.environ.get("DATABASE_PATH")
    try:
        for case in cases:
            # Every benchmark case gets a fresh database: no cross-case memory leakage.
            os.environ["DATABASE_PATH"] = str(database_dir / f"{case['id']}.sqlite3")
            result = await run_five_worlds(case["prompt"])
            results.append({"case_id": case["id"], "worlds": result["worlds"]})
    finally:
        if original_db is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = original_db
    return results


def main():
    cases = json.loads(Path("tests/fixtures/benchmark_cases.json").read_text(encoding="utf-8"))
    if not asyncio.run(model.get_client().ping()):
        raise SystemExit("Configured model endpoint is not reachable.")

    with tempfile.TemporaryDirectory(prefix="inteligen-benchmark-") as temp_dir:
        results = asyncio.run(run_cases(cases, Path(temp_dir)))

    report = evaluate_results(results, cases)
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    report["model"] = os.environ.get("MODEL_NAME", "configured-model")
    report["execution"] = "github-hosted-runner"
    report["memory_isolation"] = "one fresh SQLite database per benchmark case"
    Path("evaluation-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "all_cases_passed": report["all_cases_passed"],
        "aggregate_mean_score": report["aggregate_mean_score"],
        "per_world": report["per_world"],
        "report_file": "evaluation-report.json",
        "note": "Rubric proxy only; not a semantic correctness score.",
    }, ensure_ascii=False))
    if report["status"] != "complete":
        raise SystemExit("Evaluation output is incomplete; see evaluation-report.json.")


if __name__ == "__main__":
    main()
