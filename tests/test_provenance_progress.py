import pytest
from starlette.testclient import TestClient

from app import evaluation, memory, provenance
from app.main import app
from app.progress import summary as progress_summary
from app.worlds import WORLDS


def _new_experience(world="science"):
    return memory.record_experience(
        world=world,
        hypothesis="A testable hypothesis",
        prediction="A measurable prediction",
        expected_metric="response_time",
        predicted_value=10,
    )


def test_confirmed_experience_requires_reviewable_evidence(db):
    experience_id = _new_experience()
    with pytest.raises(ValueError, match="unknown evidence can only produce an inconclusive"):
        provenance.resolve_experience(
            experience_id, "It happened", "confirmed",
            evidence_note="A note", evidence_source_type="unknown",
            reviewer_label="reviewer",
        )
    with pytest.raises(ValueError, match="evidence_note and reviewer_label"):
        provenance.resolve_experience(
            experience_id, "It happened", "confirmed",
            evidence_source_type="manual_observation",
        )


def test_manual_evidence_is_hashed_and_marked_reviewed(db):
    experience_id = _new_experience()
    item = provenance.resolve_experience(
        experience_id, "Observed result", "confirmed", observed_value=12,
        evidence_note="Observed in the controlled test",
        evidence_source_type="manual_observation", reviewer_label="human-review",
    )
    assert item["provenance"]["validation_status"] == "reviewed"
    assert item["provenance"]["reviewer_authenticated"] is False
    assert len(item["provenance"]["evidence_sha256"]) == 64
    assert item["absolute_error"] == 2


def test_simulation_and_model_output_cannot_confirm_real_world_experience(db):
    simulation_id = _new_experience()
    with pytest.raises(ValueError, match="simulation evidence can only produce an inconclusive"):
        provenance.resolve_experience(
            simulation_id, "Simulation result", "confirmed",
            evidence_note="simulated", evidence_source_type="simulation",
            reviewer_label="reviewer",
        )
    model_id = _new_experience()
    with pytest.raises(ValueError, match="model_generated evidence can only produce an inconclusive"):
        provenance.resolve_experience(
            model_id, "Generated claim", "refuted",
            evidence_note="model said so", evidence_source_type="model_generated",
            reviewer_label="reviewer",
        )


def test_external_reference_requires_reference_and_records_provenance(db):
    experience_id = _new_experience()
    with pytest.raises(ValueError, match="requires evidence_reference"):
        provenance.resolve_experience(
            experience_id, "Observed result", "confirmed",
            evidence_note="Reviewed source", evidence_source_type="external_reference",
            reviewer_label="reviewer",
        )
    item = provenance.resolve_experience(
        experience_id, "Observed result", "refuted",
        evidence_note="Reviewed source", evidence_source_type="external_reference",
        evidence_reference="source-id:study-17", reviewer_label="reviewer",
    )
    listed = provenance.enrich(memory.experience_history("science"))
    assert listed[0]["provenance"]["evidence_sha256"] == item["provenance"]["evidence_sha256"]


def test_progress_reports_five_isolated_worlds_and_benchmark_trend(db):
    first = evaluation.evaluate_worlds({name: "concept definition hypothesis test idea option metric score gap improve" for name in WORLDS})
    second = evaluation.evaluate_worlds({name: "concept definition hypothesis test idea option metric score gap improve uncertainty evidence conclusion" for name in WORLDS})
    evaluation.record_evaluation(first, run_type="fixed_benchmark")
    evaluation.record_evaluation(second, run_type="fixed_benchmark")
    report = progress_summary()
    assert set(report["worlds"]) == set(WORLDS)
    assert report["worlds"]["knowledge"]["fixed_benchmark"]["trend"] in {"improving", "stable", "regressing"}
    assert report["worlds"]["reasoning"]["memory_records"] == 0


def test_progress_api_is_available(db):
    response = TestClient(app).get("/progress")
    assert response.status_code == 200
    assert len(response.json()["worlds"]) == 5
