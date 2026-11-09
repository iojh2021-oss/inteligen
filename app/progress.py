"""Per-world progress ledger; reports measured signals without claiming model training."""
from app import evaluation, memory, provenance
from app.worlds import WORLDS


def summary() -> dict:
    memory_counts = {
        row[0]: int(row[1])
        for row in memory._rows("SELECT world,COUNT(*) FROM memories GROUP BY world")
    }
    operational = memory.metrics_summary()
    experiences = memory.experience_summary()
    evidence = provenance.summary()
    benchmark = evaluation.evaluation_history(limit=500, run_type="fixed_benchmark")["worlds"]
    worlds = {}
    for name in WORLDS:
        history = benchmark.get(name, {})
        latest = history.get("latest", {})
        delta = history.get("score_delta")
        if delta is None:
            trend = "insufficient_data"
        elif delta > 0:
            trend = "improving"
        elif delta < 0:
            trend = "regressing"
        else:
            trend = "stable"
        worlds[name] = {
            "memory_records": memory_counts.get(name, 0),
            "operations": operational.get(name, {
                "runs": 0, "success_rate": None, "avg_latency_ms": 0, "avg_output_chars": 0
            }),
            "experiences": experiences.get(name, {}),
            "evidence": evidence.get(name, {}),
            "fixed_benchmark": {
                "latest_score": latest.get("score"),
                "previous_score": history.get("previous_score"),
                "score_delta": delta,
                "trend": trend,
                "snapshot_id": latest.get("id"),
                "benchmark_version": evaluation.FIXED_BENCHMARK_VERSION,
            },
        }
    return {
        "scope": "independent per-world memory, experience and evaluation tracking; not separate model weights or proof of intelligence",
        "worlds": worlds,
    }
