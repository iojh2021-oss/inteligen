import math

import pytest
from starlette.testclient import TestClient

from app import memory
from app.main import app


def test_experience_lifecycle_records_prediction_and_observation(db):
    item_id = memory.record_experience(
        world="science",
        hypothesis="A controlled simulation improves prediction accuracy",
        prediction="The measured error will be 2.0",
        request_id="req-123",
        expected_metric="absolute_error",
        predicted_value=2.0,
        confidence=0.8,
    )
    planned = memory.experience_history("science")[0]
    assert planned["id"] == item_id
    assert planned["outcome_status"] == "planned"
    assert planned["absolute_error"] is None

    resolved = memory.resolve_experience(
        item_id,
        observed_outcome="The simulation measured an error of 3.5",
        outcome_status="refuted",
        observed_value=3.5,
        evidence_note="Recorded from deterministic test fixture",
    )
    assert resolved["outcome_status"] == "refuted"
    assert resolved["absolute_error"] == 1.5
    assert resolved["resolved_at"] is not None


def test_experience_history_is_world_scoped(db):
    memory.record_experience("science", "climate simulation", "temperature rises")
    memory.record_experience("reasoning", "climate simulation", "causal chain")
    assert len(memory.experience_history("science")) == 1
    assert memory.experience_history("science")[0]["world"] == "science"


def test_experience_cannot_be_resolved_twice(db):
    item_id = memory.record_experience("knowledge", "hypothesis", "prediction")
    memory.resolve_experience(item_id, "observed", "confirmed")
    with pytest.raises(ValueError, match="already resolved"):
        memory.resolve_experience(item_id, "second observation", "refuted")


def test_experience_rejects_unknown_world_and_invalid_confidence(db):
    with pytest.raises(ValueError, match="Unknown world"):
        memory.record_experience("unknown", "hypothesis", "prediction")
    with pytest.raises(ValueError, match="confidence"):
        memory.record_experience("science", "hypothesis", "prediction", confidence=1.1)
    with pytest.raises(ValueError, match="finite"):
        memory.record_experience("science", "hypothesis", "prediction", confidence=math.nan)


def test_experience_summary_reports_status_and_prediction_error(db):
    item_id = memory.record_experience(
        "science", "numeric prediction", "predict 10", predicted_value=10
    )
    memory.resolve_experience(item_id, "observed 13", "confirmed", observed_value=13)
    memory.record_experience("science", "another hypothesis", "future result")
    summary = memory.experience_summary()["science"]
    assert summary["confirmed"] == 1
    assert summary["planned"] == 1
    assert summary["resolved"] == 1
    assert summary["mean_absolute_error"] == 3.0


def test_experience_api_create_resolve_history_and_summary(db):
    client = TestClient(app)
    created = client.post("/experiences", json={
        "world": "science",
        "hypothesis": "A simulation predicts the measured value",
        "prediction": "The value will be 5",
        "predicted_value": 5,
        "confidence": 0.7,
    })
    assert created.status_code == 201
    item_id = created.json()["id"]

    resolved = client.post(f"/experiences/{item_id}/resolve", json={
        "observed_outcome": "The measured value was 7",
        "outcome_status": "refuted",
        "observed_value": 7,
        "evidence_note": "Fixed test observation",
    })
    assert resolved.status_code == 200
    assert resolved.json()["absolute_error"] == 2

    history = client.get("/experiences?world=science").json()["items"]
    assert history[0]["outcome_status"] == "refuted"
    summary = client.get("/experiences/summary").json()["worlds"]
    assert summary["science"]["refuted"] == 1


def test_experience_api_rejects_invalid_input(db):
    client = TestClient(app)
    assert client.post("/experiences", json={
        "world": "not-a-world", "hypothesis": "h", "prediction": "p"
    }).status_code == 422
    assert client.get("/experiences?world=not-a-world").status_code == 422
    assert client.post("/experiences/999/resolve", json={
        "observed_outcome": "x", "outcome_status": "confirmed"
    }).status_code == 422



def test_orchestrator_injects_only_the_current_world_experience(fake):
    import asyncio

    from app.orchestrator import run_five_worlds

    memory.record_experience(
        "science",
        "The controlled simulation predicts lower variance",
        "Variance will decrease by 20 percent",
    )
    asyncio.run(run_five_worlds("Review the simulation"))
    science_prompt = next(
        prompt for system, prompt in fake.calls if "Science World" in system
    )
    knowledge_prompt = next(
        prompt for system, prompt in fake.calls if "Knowledge World" in system
    )
    assert "controlled simulation predicts lower variance" in science_prompt
    assert "controlled simulation predicts lower variance" not in knowledge_prompt
