import pytest
from starlette.testclient import TestClient

from app import simulation
from app.main import app


def test_logistic_simulation_is_deterministic_and_persisted(db):
    params = {
        "initial_population": 10,
        "growth_rate": 0.2,
        "carrying_capacity": 100,
        "steps": 12,
    }
    first = simulation.run_simulation("logistic_population", params)
    second = simulation.run_simulation("logistic_population", params)
    assert first["fingerprint"] == second["fingerprint"]
    assert first["result"] == second["result"]
    assert len(first["result"]["series"]) == 13
    assert simulation.get_run(first["run_id"])["fingerprint"] == first["fingerprint"]


def test_decay_simulation_respects_rate_and_steps(db):
    result = simulation.run_simulation("exponential_decay", {
        "initial_value": 100,
        "decay_rate": 0.1,
        "steps": 2,
    })
    assert result["result"]["series"] == [100.0, 90.0, 81.0]
    assert result["result"]["final_value"] == 81.0


def test_simulation_rejects_unknown_scenario_and_invalid_parameters(db):
    with pytest.raises(ValueError, match="Unknown simulation"):
        simulation.run_simulation("arbitrary_python", {})
    with pytest.raises(ValueError, match="Unknown parameters"):
        simulation.run_simulation("exponential_decay", {
            "initial_value": 10, "decay_rate": 0.1, "steps": 2, "code": "print(1)"
        })
    with pytest.raises(ValueError, match="outside"):
        simulation.run_simulation("exponential_decay", {
            "initial_value": 10, "decay_rate": 2, "steps": 2
        })


def test_simulation_rejects_non_finite_and_excessive_inputs(db):
    with pytest.raises(ValueError, match="finite"):
        simulation.run_simulation("exponential_decay", {
            "initial_value": float("nan"), "decay_rate": 0.1, "steps": 2
        })
    with pytest.raises(ValueError, match="outside"):
        simulation.run_simulation("logistic_population", {
            "initial_population": 1e20,
            "growth_rate": 0.2,
            "carrying_capacity": 100,
            "steps": 5,
        })


def test_simulation_api_lists_runs_and_returns_saved_run(db):
    client = TestClient(app)
    scenarios = client.get("/simulations/scenarios")
    assert scenarios.status_code == 200
    assert "logistic_population" in scenarios.json()["scenarios"]

    created = client.post("/simulations/run", json={
        "scenario": "exponential_decay",
        "parameters": {"initial_value": 80, "decay_rate": 0.25, "steps": 2},
    })
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    fetched = client.get(f"/simulations/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["fingerprint"] == created.json()["fingerprint"]


def test_simulation_api_rejects_bad_input_and_unknown_run(db):
    client = TestClient(app)
    assert client.post("/simulations/run", json={"scenario": "missing", "parameters": {}}).status_code == 422
    assert client.get("/simulations/999").status_code == 404



def test_simulation_result_is_attached_as_inconclusive_experience(db):
    client = TestClient(app)
    created = client.post("/simulations/run", json={
        "scenario": "exponential_decay",
        "parameters": {"initial_value": 100, "decay_rate": 0.2, "steps": 1},
    })
    run_id = created.json()["run_id"]

    attached = client.post(f"/simulations/{run_id}/experience", json={
        "world": "science",
        "hypothesis": "The decay model reduces the measured quantity",
        "prediction": "The final value will be 80",
        "expected_metric": "final_value",
        "predicted_value": 80,
        "confidence": 0.9,
    })
    assert attached.status_code == 201
    item = attached.json()
    assert item["outcome_status"] == "inconclusive"
    assert item["observed_value"] == 80
    assert "Simulation-only evidence" in item["evidence_note"]
    assert item["request_id"].startswith("simulation:")


def test_simulation_experience_rejects_missing_run(db):
    client = TestClient(app)
    response = client.post("/simulations/999/experience", json={
        "world": "science",
        "hypothesis": "A hypothesis",
        "prediction": "A prediction",
    })
    assert response.status_code == 422
