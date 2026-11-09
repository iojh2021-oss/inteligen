"""Central configuration, read lazily from the environment so tests can override it."""
import os
from pathlib import Path


def model_base_url() -> str:
    return os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")


def model_name() -> str:
    return os.getenv("MODEL_NAME", "qwen3:4b")


def model_api_key() -> str:
    return os.getenv("MODEL_API_KEY", "")


def request_timeout() -> float:
    return float(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))


def database_path() -> str:
    return os.getenv("DATABASE_PATH", "data/memory.sqlite3")


def world_concurrency() -> int:
    """How many worlds may call the model at once. 1 is safest for small local models."""
    try:
        return max(1, int(os.getenv("WORLD_CONCURRENCY", "1")))
    except ValueError:
        return 1


def evolution_dir() -> str:
    """Where versioned configs, proposals, benchmark and history live (committed to Git)."""
    default = str(Path(__file__).resolve().parent.parent / "evolution")
    return os.getenv("EVOLUTION_DIR", default)


def lab_max_questions() -> int:
    try:
        return max(1, int(os.getenv("LAB_MAX_QUESTIONS", "2")))
    except ValueError:
        return 2
