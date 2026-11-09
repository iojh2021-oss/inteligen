import pytest

from app import model


class FakeModel:
    """Deterministic stand-in for the local model. Answers depend on the system prompt."""

    def __init__(self, fail_worlds=()):
        self.calls = []  # (system_prompt, user_prompt)
        self.fail_worlds = set(fail_worlds)

    async def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        for name in ("Knowledge", "Reasoning", "Science", "Creativity", "Learning"):
            if f"You are the {name} World" in system_prompt:
                if name.lower() in self.fail_worlds:
                    raise model.ModelUnavailable(f"{name} down")
                return f"answer-from-{name.lower()}"
        if "central coordinator" in system_prompt:
            if "central" in self.fail_worlds:
                raise model.ModelUnavailable("central down")
            return "final-synthesis"
        return "unknown"

    async def ping(self):
        return True


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("EVOLUTION_DIR", str(tmp_path / "evolution"))
    return tmp_path


@pytest.fixture
def fake(db):
    original = model.get_client()
    client = FakeModel()
    model.set_client(client)
    yield client
    model.set_client(original)
