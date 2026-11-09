"""Central brain: routes one request to all worlds, runs them in dependency order,
records per-world metrics, isolates failures, and synthesizes the final answer."""
import asyncio
import time
import uuid

from app import config, memory, model
from app.worlds import WORLDS, World

SYNTHESIS_PROMPT = (
    "You are the central coordinator of five specialist worlds. Synthesize their results, "
    "resolve disagreements explicitly, preserve uncertainty, and give a concise useful answer. "
    "Do not claim tests were run unless evidence is provided. If a world is marked unavailable, "
    "say what is missing instead of guessing it."
)


def _memory_context(world: World, question: str) -> str:
    items = memory.relevant(world.name, question)
    experiences = memory.experience_history(world.name, question, limit=3)
    sections = []
    if items:
        sections.append(
            "Prior work (may be outdated or wrong; verify it):\n"
            + "\n".join(
                f"[{m['created_at'][:10]}] {m['result'][:700]}" for m in items
            )
        )
    if experiences:
        lines = []
        for item in experiences:
            observed = item["observed_outcome"] or "not observed yet"
            lines.append(
                f"Status={item['outcome_status']}; hypothesis={item['hypothesis']}; "
                f"prediction={item['prediction']}; observation={observed}; "
                f"numeric_absolute_error={item['absolute_error']}"
            )
        sections.append(
            "Prior experiment records (evidence notes are records, not guaranteed truth):\n"
            + "\n".join(lines)
        )
    return "\n\n".join(sections) if sections else "No relevant prior work or experience records."


def _build_prompt(world: World, question: str, outputs: dict, errors: dict) -> str:
    parts = [
        f"User task:\n{question}",
        "Your own relevant past work (may be outdated or wrong; verify it):\n"
        + _memory_context(world, question),
    ]
    if world.depends_on:
        lines = []
        for dep in world.depends_on:
            if dep in outputs:
                lines.append(f"{dep.upper()} WORLD:\n{outputs[dep]}")
            else:
                lines.append(f"{dep.upper()} WORLD: unavailable ({errors.get(dep, 'not run')})")
        parts.append("Outputs from other worlds to review:\n\n" + "\n\n".join(lines))
    return "\n\n".join(parts)


async def run_five_worlds(question: str):
    request_id = uuid.uuid4().hex[:12]
    sem = asyncio.Semaphore(config.world_concurrency())
    outputs: dict = {}
    errors: dict = {}

    async def run_world(world: World):
        prompt = _build_prompt(world, question, outputs, errors)
        started = time.monotonic()
        async with sem:
            try:
                answer = await model.generate(world.system_prompt, prompt)
            except model.ModelUnavailable as exc:
                errors[world.name] = str(exc)
                memory.record_metric(world.name, request_id, False,
                                     int((time.monotonic() - started) * 1000), 0)
                return
        outputs[world.name] = answer
        memory.record_metric(world.name, request_id, True,
                             int((time.monotonic() - started) * 1000), len(answer))
        memory.save(world.name, question, answer, request_id)

    pending = dict(WORLDS)
    while pending:
        ready = [w for w in pending.values()
                 if all(d in outputs or d in errors for d in w.depends_on)]
        if not ready:  # defensive: dependency cycle
            raise RuntimeError("Circular world dependencies")
        await asyncio.gather(*(run_world(w) for w in ready))
        for w in ready:
            pending.pop(w.name)

    if not outputs:
        raise model.ModelUnavailable("All worlds failed: " + "; ".join(errors.values()))

    sections = []
    for name in WORLDS:
        if name in outputs:
            sections.append(f"{name.upper()} WORLD:\n{outputs[name]}")
        else:
            sections.append(f"{name.upper()} WORLD: unavailable ({errors.get(name)})")
    synthesis = await model.generate(
        SYNTHESIS_PROMPT, "Question:\n" + question + "\n\n" + "\n\n".join(sections)
    )
    memory.save("central", question, synthesis, request_id)
    return {
        "request_id": request_id,
        "answer": synthesis,
        "worlds": {name: outputs.get(name, f"(unavailable: {errors.get(name)})") for name in WORLDS},
        "errors": errors,
    }
