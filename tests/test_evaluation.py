from app.evaluation import evaluate_text, evaluate_worlds


def test_world_rubric_returns_transparent_checks():
    result = evaluate_text(
        "science",
        "Hypothesis: X. Prediction: Y. Run a safe experiment and measure it. Limitation: small sample.",
    )
    assert result["score"] == 100
    assert result["passed"] == result["total"]
    assert result["missing"] == []
    assert "not truth" in result["interpretation"]


def test_missing_criteria_are_reported():
    result = evaluate_text("reasoning", "This is a conclusion.")
    assert result["score"] < 100
    assert "ordered_steps" in result["missing"]
    assert result["checks"]["conclusion"] is True


def test_unavailable_world_is_not_given_a_zero_quality_score():
    result = evaluate_worlds({
        "knowledge": "Concepts and verified facts with evidence and uncertainty.",
        "reasoning": "(unavailable: model down)",
        "science": "Hypothesis, prediction, experiment, limitation.",
        "creativity": "Several ideas, trade-offs, combine and practical approach.",
        "learning": "Gap, measurable metric, evaluation test and improvement.",
    })
    assert result["worlds"]["reasoning"]["status"] == "unavailable"
    assert result["worlds"]["reasoning"]["score"] is None
    assert result["evaluated_worlds"] == 4


def test_evaluation_snapshots_track_same_rubric_delta(db):
    from app.evaluation import evaluation_history, record_evaluation

    first = evaluate_worlds({
        "knowledge": "Concept definition, verified fact, evidence, uncertainty.",
    })
    record_evaluation(first)
    second = evaluate_worlds({
        "knowledge": "Concept definition and verified fact with evidence; uncertainty remains.",
    })
    record_evaluation(second)
    history = evaluation_history()
    item = history["worlds"]["knowledge"]
    assert item["latest"]["rubric_version"] == 1
    assert item["score_delta"] == 0


def test_evaluation_api_persists_snapshot_and_history(db):
    from starlette.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post("/evaluations", json={"worlds": {
        "science": "Hypothesis, prediction, experiment, measurement and limitation."
    }})
    assert response.status_code == 201
    assert "snapshot_ids" in response.json()["persistence"]
    history = client.get("/evaluations/history").json()
    assert history["worlds"]["science"]["latest"]["score"] == 100


def test_evaluation_rejects_non_object_worlds(db):
    from starlette.testclient import TestClient
    from app.main import app

    assert TestClient(app).post("/evaluations", json={"worlds": []}).status_code == 422


def test_ask_response_includes_and_persists_evaluation(fake, db):
    from starlette.testclient import TestClient
    from app.main import app
    from app.evaluation import evaluation_history

    response = TestClient(app).post("/ask", json={"question": "Explain a safe science concept."})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["evaluation"]["worlds"]) == {
        "knowledge", "reasoning", "science", "creativity", "learning"
    }
    assert len(evaluation_history()["worlds"]) == 5
