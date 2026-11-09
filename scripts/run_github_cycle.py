"""Run Inteligen entirely on a temporary GitHub-hosted runner.

The runner uses a local Ollama model; no external inference server is required.
The SQLite memory and dashboard snapshots are persisted by the workflow commit.
Do not send secrets or private personal information: this repository is public.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app import memory, model
from app.orchestrator import run_five_worlds


def main() -> None:
    question = os.environ.get("BRAIN_QUESTION", "").strip()
    if not 2 <= len(question) <= 6000:
        raise SystemExit("BRAIN_QUESTION must contain 2 to 6000 characters.")

    if not asyncio.run(model.get_client().ping()):
        raise SystemExit("The local Ollama OpenAI-compatible endpoint is not reachable.")

    result = asyncio.run(run_five_worlds(question))
    timestamp = datetime.now(timezone.utc).isoformat()
    state = {
        "timestamp": timestamp,
        "request_id": result["request_id"],
        "model": os.environ.get("MODEL_NAME", "qwen3:1.7b"),
        "execution": "github-hosted-runner",
        "question": question,
        "answer": result["answer"],
        "worlds": result["worlds"],
        "errors": result["errors"],
    }

    state_dir = Path("docs/state")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "latest.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metrics = {
        "updated_at": timestamp,
        "worlds": memory.metrics_summary(),
        "memory_items": len(memory.recent(100)),
        "architecture": "central-brain + five-worlds + sqlite-long-term-memory",
    }
    (state_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": True,
        "request_id": result["request_id"],
        "successful_worlds": [k for k, v in result["worlds"].items()
                              if not str(v).startswith("(unavailable:")],
        "failed_worlds": result["errors"],
        "memory_path": os.environ.get("DATABASE_PATH", "data/memory.sqlite3"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
