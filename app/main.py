from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from app.orchestrator import run_five_worlds
from app.memory import recent
from app.model import ModelUnavailable

load_dotenv()
app = FastAPI(title="Five Worlds — One Evolving AI", version="0.1.0")

class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=6000)

@app.get("/", response_class=HTMLResponse)
async def home():
    return Path("static/index.html").read_text(encoding="utf-8")

@app.get("/health")
async def health():
    return {"ok": True, "project": "five-worlds-one-ai", "worlds": 5, "model_configured": True}

@app.get("/memory")
async def memory():
    return {"items": recent(30)}

@app.post("/ask")
async def ask(body: AskRequest):
    try:
        return await run_five_worlds(body.question)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
