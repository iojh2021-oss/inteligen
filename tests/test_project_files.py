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
