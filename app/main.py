from pathlib import Path

from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

load_dotenv()  # must run before app modules read the environment

from app import memory, model  # noqa: E402
from app.orchestrator import run_five_worlds  # noqa: E402
from app.worlds import WORLDS  # noqa: E402

_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


def _error(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


async def home(request):
    return HTMLResponse(_INDEX.read_text(encoding="utf-8"))


async def health(request):
    return JSONResponse({"ok": True, "project": "five-worlds-one-ai", "worlds": len(WORLDS)})


async def health_model(request):
    return JSONResponse({"model_reachable": await model.get_client().ping()})


async def get_memory(request):
    return JSONResponse({"items": memory.recent(30)})


async def forget_memory(request):
    try:
        memory_id = int(request.path_params["memory_id"])
    except ValueError:
        return _error(422, "memory_id must be an integer")
    if not memory.forget(memory_id):
        return _error(404, "Memory not found")
    return JSONResponse({"deleted": memory_id})


async def metrics(request):
    return JSONResponse({"worlds": memory.metrics_summary()})


async def ask(request):
    try:
        body = await request.json()
    except ValueError:
        return _error(422, "Body must be valid JSON")
    question = body.get("question") if isinstance(body, dict) else None
    if not isinstance(question, str) or not (2 <= len(question) <= 6000):
        return _error(422, "question must be a string of 2 to 6000 characters")
    try:
        return JSONResponse(await run_five_worlds(question))
    except model.ModelUnavailable as exc:
        return _error(503, str(exc))


app = Starlette(routes=[
    Route("/", home),
    Route("/health", health),
    Route("/health/model", health_model),
    Route("/memory", get_memory),
    Route("/memory/{memory_id}", forget_memory, methods=["DELETE"]),
    Route("/metrics", metrics),
    Route("/ask", ask, methods=["POST"]),
])
