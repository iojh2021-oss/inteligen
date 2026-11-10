import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_has_no_literal_backslash_n_join_bug():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "join('\\\\n')" not in html and 'join("\\\\n")' not in html


def test_pages_deploy_jobs_declare_the_github_pages_environment():
    for name in ("github-brain.yml", "evolution.yml", "pages.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert re.search(r"environment:\s*\n\s*name: github-pages", text), name


def test_brain_workflow_does_not_run_the_whole_model_on_every_push():
    text = (ROOT / ".github" / "workflows" / "github-brain.yml").read_text(encoding="utf-8")
    assert "push:" not in text.split("jobs:")[0]


def test_committed_state_is_valid_json_and_baseline_exists():
    for rel in ("docs/state/latest.json", "docs/state/metrics.json",
                "evolution/stable.json", "evolution/versions/v1.json",
                "evolution/benchmark.json", "evolution/history.json"):
        json.loads((ROOT / rel).read_text(encoding="utf-8"))
    assert json.loads((ROOT / "evolution/stable.json").read_text())["version"] >= 1


def test_workflows_never_push_to_the_protected_branch_directly():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "git push" not in text, path.name


def test_state_workflows_sync_through_the_state_branch():
    for name in ("github-brain.yml", "evolution.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "state_sync.sh pull" in text and "state_sync.sh push" in text, name
    script = (ROOT / "scripts" / "state_sync.sh").read_text(encoding="utf-8")
    assert "refs/heads/$BRANCH" in script and "refs/heads/main" not in script


def _text(name):
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_brain_workflow_is_scheduled_manual_bounded_and_serialized():
    text = _text("github-brain.yml")
    assert "workflow_dispatch:" in text
    cron = re.search(r'- cron: "([^"]+)"', text).group(1)
    assert len(cron.split()) == 5
    assert int(re.search(r"timeout-minutes: (\d+)", text).group(1)) <= 90
    assert re.search(r"concurrency:\s*\n\s*group: inteligen-state\s*\n\s*cancel-in-progress: false", text)
    assert "vars.LEARNING_PAUSED" in text


def test_scheduled_learning_cannot_trigger_itself_or_loop():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("gh workflow run", "workflow_run:", "repository_dispatch", "actions/workflows/"):
            assert forbidden not in text, (path.name, forbidden)
        assert "while true" not in text and "sleep 3600" not in text


def test_permissions_are_explicit_and_minimal():
    for name in ("github-brain.yml", "evolution.yml", "pages.yml", "tests.yml"):
        text = _text(name)
        assert re.search(r"^permissions:\s*\n(\s+[a-z-]+: (read|write)\s*\n)+", text, re.M), name
        assert "write-all" not in text and "secrets." not in text, name


def test_cycle_retry_is_limited_to_one_and_state_is_validated_before_push():
    text = _text("github-brain.yml")
    assert text.count("run_github_cycle.py") == 2  # first attempt + exactly one retry
    assert text.index("validate_state.py") < text.index("state_sync.sh push")


def test_no_always_on_service_is_configured():
    banned = ("render.yaml", "Procfile", "fly.toml", "docker-compose.yml", "railway.json")
    assert not [name for name in banned if (ROOT / name).exists()]
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert "ssh " not in path.read_text(encoding="utf-8"), path.name


def test_dashboard_reads_real_status_and_flags_stale_or_missing_data():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "status.json" in html and "stale" in html and "never" in html
    assert "not an always-on server" in html
