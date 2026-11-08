from starlette.testclient import TestClient

from app.main import app


def test_health(fake):
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["worlds"] == 5


def test_ask_end_to_end_then_metrics_and_forget(fake):
    c = TestClient(app)
    r = c.post("/ask", json={"question": "what is entropy"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "final-synthesis" and len(body["worlds"]) == 5

    items = c.get("/memory").json()["items"]
    assert len(items) == 6
    assert c.get("/metrics").json()["worlds"]["knowledge"]["runs"] == 1

    assert c.delete(f"/memory/{items[0]['id']}").status_code == 200
    assert c.delete(f"/memory/{items[0]['id']}").status_code == 404


def test_ask_returns_503_when_model_is_down(fake):
    fake.fail_worlds = {"knowledge", "reasoning", "science", "creativity", "learning"}
    r = TestClient(app).post("/ask", json={"question": "what is entropy"})
    assert r.status_code == 503


def test_ask_validates_input(fake):
    assert TestClient(app).post("/ask", json={"question": "x"}).status_code == 422


def test_home_page_is_served(fake):
    assert "Five Worlds" in TestClient(app).get("/").text
