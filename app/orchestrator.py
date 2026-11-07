from app.worlds import WORLDS
from app.model import generate
from app.memory import save, recent

async def run_five_worlds(question: str):
    history = recent(5)
    context = "\n".join(f"[{m['world']}] {m['result'][:700]}" for m in history)
    outputs = {}
    for world, system in WORLDS.items():
        prompt = f"User task:\n{question}\n\nRecent shared memory (may be incomplete; verify it):\n{context or 'No prior memory.'}"
        answer = await generate(system, prompt)
        outputs[world] = answer
        save(world, question, answer)
    synthesis = await generate(
        "You are the central coordinator of five specialist worlds. Synthesize their results, resolve disagreements explicitly, preserve uncertainty, and give a concise useful answer. Do not claim tests were run unless evidence is provided.",
        "Question:\n" + question + "\n\n" + "\n\n".join(f"{k.upper()} WORLD:\n{v}" for k,v in outputs.items())
    )
    save("central", question, synthesis)
    return {"answer": synthesis, "worlds": outputs}
