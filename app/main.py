from pathlib import Path

from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

load_dotenv()  # must run before app modules read the environment

from app import memory, model, simulation  # noqa: E402
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


async def get_experiences(request):
    world = request.query_params.get("world", "")
    question = request.query_params.get("q")
    if world not in WORLDS:
        return _error(422, "world must be one of: " + ", ".join(WORLDS))
    try:
        limit = int(request.query_params.get("limit", "10"))
        return JSONResponse({
            "world": world,
            "items": memory.experience_history(world, question, limit),
        })
    except (TypeError, ValueError) as exc:
        return _error(422, str(exc))


async def create_experience(request):
    try:
        body = await request.json()
    except ValueError:
        return _error(422, "Body must be valid JSON")
    if not isinstance(body, dict):
        return _error(422, "Body must be a JSON object")
    try:
        experience_id = memory.record_experience(
            world=body.get("world"),
            hypothesis=body.get("hypothesis"),
            prediction=body.get("prediction"),
            request_id=body.get("request_id"),
            expected_metric=body.get("expected_metric"),
            predicted_value=body.get("predicted_value"),
            confidence=body.get("confidence"),
        )
    except (TypeError, ValueError) as exc:
        return _error(422, str(exc))
    return JSONResponse({"id": experience_id, "status": "planned"}, status_code=201)


async def resolve_experience(request):
    try:
        experience_id = int(request.path_params["experience_id"])
    except ValueError:
        return _error(422, "experience_id must be an integer")
    try:
        body = await request.json()
    except ValueError:
        return _error(422, "Body must be valid JSON")
    if not isinstance(body, dict):
        return _error(422, "Body must be a JSON object")
    try:
        item = memory.resolve_experience(
            experience_id=experience_id,
            observed_outcome=body.get("observed_outcome"),
            outcome_status=body.get("outcome_status"),
            observed_value=body.get("observed_value"),
            evidence_note=body.get("evidence_note"),
        )
    except (TypeError, ValueError) as exc:
        return _error(422, str(exc))
    return JSONResponse(item)


async def experience_summary(request):
    return JSONResponse({"worlds": memory.experience_summary()})


async def list_simulations(request):
    return JSONResponse({"scenarios": simulation.SCENARIOS})


async def run_simulation(request):
    try:
        body = await request.json()
    except ValueError:
        return _error(422, "Body must be valid JSON")
    if not isinstance(body, dict):
        return _error(422, "Body must be a JSON object")
    try:
        result = simulation.run_simulation(
            body.get("scenario"), body.get("parameters", {})
        )
    except (TypeError, ValueError) as exc:
        return _error(422, str(exc))
    return JSONResponse(result, status_code=201)


async def get_simulation(request):
    try:
        run_id = int(request.path_params["run_id"])
    except ValueError:
        return _error(422, "run_id must be an integer")
    result = simulation.get_run(run_id)
    if result is None:
        return _error(404, "Simulation run not found")
    return JSONResponse(result)


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
    Route("/experiences", get_experiences, methods=["GET"]),
    Route("/experiences", create_experience, methods=["POST"]),
    Route("/experiences/summary", experience_summary, methods=["GET"]),
    Route("/simulations/scenarios", list_simulations, methods=["GET"]),
    Route("/simulations/run", run_simulation, methods=["POST"]),
    Route("/simulations/{run_id}", get_simulation, methods=["GET"]),
    Route("/experiences/{experience_id}/resolve", resolve_experience, methods=["POST"]),
    Route("/ask", ask, methods=["POST"]),
])
