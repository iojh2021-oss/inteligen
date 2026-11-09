"""Simulation laboratory: isolated, repeatable runs of the five worlds on a fixed benchmark.

Isolation rules (enforced by orchestrator lab mode): no memory reads or writes, no metrics,
no central synthesis, no tools, no shell. The lab only produces text and rubric scores.
"""
import json
from pathlib import Path

from app import config, evaluation
from app.orchestrator import run_five_worlds
from app.worlds import WORLDS

EXCERPT_CHARS = 600


def load_benchmark() -> list:
    path = Path(config.evolution_dir()) / "benchmark.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = [q["question"] for q in data["questions"] if isinstance(q.get("question"), str)]
    return questions[: config.lab_max_questions()]


async def run_benchmark(additions: dict, questions: list) -> dict:
    """Run every question once with the given prompt additions and score each world."""
    runs = []
    for index, question in enumerate(questions):
        result = await run_five_worlds(question, additions=additions, lab=True)
        report = evaluation.evaluate_worlds(result["worlds"])
        runs.append({
            "index": index,
            "question": question,
            "errors": result["errors"],
            "scores": {w: report["worlds"][w]["score"] for w in WORLDS},
            "missing": {w: report["worlds"][w]["missing"] for w in WORLDS},
            "excerpts": {w: str(result["worlds"][w])[:EXCERPT_CHARS] for w in WORLDS},
        })
    return {"runs": runs}
