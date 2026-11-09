from starlette.testclient import TestClient

from app.main import app


def test_lab_history_endpoint(fake):
    response = TestClient(app).get("/lab/experiments")
    assert response.status_code == 200
    assert response.json() == {"experiments": []}


def test_lab_compare_rejects_empty_and_oversized_candidate(fake):
    client = TestClient(app)
    assert client.post("/lab/compare", json={}).status_code == 422
    assert client.post("/lab/compare", json={"candidate_instruction": "x" * 1201}).status_code == 422


def test_lab_compare_endpoint_runs_isolated_experiment(fake):
    response = TestClient(app).post(
        "/lab/compare",
        json={"candidate_instruction": "Use concise headings and state limitations."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["promotion"] == "not_performed"
    assert len(body["worlds"]) == 5
    assert TestClient(app).get("/lab/experiments").json()["experiments"][0]["experiment_id"] == body["experiment_id"]
