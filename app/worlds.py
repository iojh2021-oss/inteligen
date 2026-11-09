"""World definitions. Each world has a name, a system prompt, and the worlds whose
output it needs (depends_on). Worlds without dependencies run first."""
from dataclasses import dataclass


@dataclass(frozen=True)
class World:
    name: str
    system_prompt: str
    depends_on: tuple = ()


_BASE = {
    "knowledge": "You are the Knowledge World. Extract relevant concepts, distinguish verified facts from assumptions, state uncertainty, and never invent sources.",
    "reasoning": "You are the Reasoning World. Break the problem into steps, check assumptions and logic, and identify what would falsify the conclusion.",
    "science": "You are the Science World. Form testable hypotheses, propose safe and ethical desk-based or simulated tests, predict outcomes, and state limitations.",
    "creativity": "You are the Creativity World. Generate several original, practical approaches and explain trade-offs without presenting speculation as fact.",
    "learning": "You are the Learning World. Review the other worlds' outputs, identify gaps, propose measurable evaluation tests and reversible configuration/prompt improvements. Do not modify code, deploy, execute commands, or grant permissions.",
}

WORLDS = {
    name: World(
        name=name,
        system_prompt=prompt,
        # Learning reviews the other four, so it must run after them.
        depends_on=("knowledge", "reasoning", "science", "creativity") if name == "learning" else (),
    )
    for name, prompt in _BASE.items()
}


MAX_ADDITION_CHARS = 700


def system_prompt(name: str, additions: dict = None) -> str:
    """Base prompt plus human-approved guidance for this world (from the stable version)."""
    base = WORLDS[name].system_prompt
    extra = str((additions or {}).get(name, "")).strip()[:MAX_ADDITION_CHARS]
    if not extra:
        return base
    return base + "\n\nAdditional approved guidance:\n" + extra
