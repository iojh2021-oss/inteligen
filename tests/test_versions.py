import pytest

from app import versions


def make_proposal(pid="p-1", status="recommended", base=1, additions=None):
    versions.ensure_baseline()
    versions.save_proposal({
        "id": pid, "created_at": "2026-01-01T00:00:00", "status": status, "base_version": base,
        "candidate_additions": additions or {"science": "- State a clear, testable hypothesis."},
    })


def test_default_stable_is_baseline_without_additions(db):
    cfg = versions.load_stable()
    assert cfg["version"] == 1 and cfg["world_additions"] == {}


def test_ensure_baseline_creates_v1_for_rollback(db):
    versions.ensure_baseline()
    assert [v["version"] for v in versions.list_versions()] == [1]


def test_additions_are_cleaned_and_bounded():
    cleaned = versions.clean_additions({"science": "x" * 5000, "hacker": "rm -rf", "reasoning": 5})
    assert list(cleaned) == ["science"] and len(cleaned["science"]) == 700


def test_promote_requires_recommended_status_and_an_approver(db):
    make_proposal(status="inconclusive")
    with pytest.raises(versions.VersionError):
        versions.promote("p-1", "alice")
    make_proposal(status="recommended")
    with pytest.raises(versions.VersionError):
        versions.promote("p-1", "")


def test_promote_creates_new_version_and_marks_proposal(db):
    make_proposal()
    new = versions.promote("p-1", "alice")
    assert new["version"] == 2 and new["approved_by"] == "alice"
    assert versions.stable_additions() == {"science": "- State a clear, testable hypothesis."}
    assert versions.load_proposal("p-1")["status"] == "promoted"
    assert [v["version"] for v in versions.list_versions()] == [1, 2]


def test_stale_proposal_cannot_be_promoted(db):
    make_proposal("p-1")
    make_proposal("p-2")
    versions.promote("p-1", "alice")
    with pytest.raises(versions.VersionError):
        versions.promote("p-2", "alice")


def test_rollback_restores_old_additions_as_a_new_version(db):
    make_proposal()
    versions.promote("p-1", "alice")
    restored = versions.rollback(1, "alice")
    assert restored["version"] == 3 and restored["restored_from"] == 1
    assert versions.stable_additions() == {}
    with pytest.raises(versions.VersionError):
        versions.rollback(99, "alice")


def test_proposal_ids_cannot_escape_the_folder(db):
    with pytest.raises(versions.VersionError):
        versions.load_proposal("../stable")
