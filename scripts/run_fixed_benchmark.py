"""Run the fixed five-world benchmark on a temporary GitHub Actions runner.

The report is an auditable rubric snapshot, not proof of factual correctness or learning.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config, evaluation, model  # noqa: E402


async def main() -> int:
    output_dir = Path(os.getenv("BENCHMARK_OUTPUT_DIR", "artifacts"))
    output_dir.mkdir(parents=True, exist_ok=True)

    client = model.get_client()
    if not await client.ping():
        raise RuntimeError("Configured model endpoint did not respond to /models")

    report = await evaluation.run_fixed_benchmark(client)
    persistence = evaluation.record_evaluation(report, run_type="fixed_benchmark")
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": config.model_name(),
        "benchmark_version": evaluation.FIXED_BENCHMARK_VERSION,
        "report": report,
        "persistence": persistence,
        "interpretation": (
            "Rubric coverage is a structural text signal only; it does not establish "
            "truth, factual correctness, intelligence, or learning."
        ),
    }
    destination = output_dir / "fixed-benchmark.json"
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "artifact": str(destination),
        "model": payload["model"],
        "evaluated_worlds": report["evaluated_worlds"],
        "expected_worlds": 5,
        "overall_score": report["overall_score"],
        "snapshot_ids": persistence["snapshot_ids"],
    }, ensure_ascii=False))

    # Preserve the report even when a world was unavailable; fail the job so
    # a partial benchmark cannot be mistaken for a complete five-world run.
    return 0 if report["evaluated_worlds"] == 5 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
