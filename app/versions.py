"""Versioned configuration for the five worlds, stored as plain JSON files in Git.

A *version* is a set of per-world prompt additions. The stable version is what production
cycles use. Candidates are proposed and evaluated by the evolution engine, but only a human
(who can run the Evolution workflow) can promote one or roll back. Model output never becomes
configuration: additions come from a fixed, reviewable instruction library.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.worlds import MAX_ADDITION_CHARS, WORLDS


class VersionError(ValueError):
    pass


def _dir() -> Path:
    return Path(config.evolution_dir())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_additions(additions) -> dict:
    """Keep only known worlds, strings, and a bounded length."""
    out = {}
    for name, text in (additions or {}).items():
        if name in WORLDS and isinstance(text, str) and text.strip():
            out[name] = text.strip()[:MAX_ADDITION_CHARS]
    return out


def default_stable() -> dict:
    return {"version": 1, "created_at": None, "note": "baseline prompts, no additions",
            "world_additions": {}}


def load_stable() -> dict:
    path = _dir() / "stable.json"
    if not path.exists():
        return default_stable()
    data = _read(path)
    data["world_additions"] = clean_additions(data.get("world_additions"))
    return data


def stable_additions() -> dict:
    return load_stable()["world_additions"]


def _save_stable(cfg: dict) -> None:
    _write(_dir() / "stable.json", cfg)
    _write(_dir() / "versions" / f"v{cfg['version']}.json", cfg)


def ensure_baseline() -> dict:
    """Create stable.json (v1) on first use so that rollback to v1 always works."""
    path = _dir() / "stable.json"
    if path.exists():
        return load_stable()
    cfg = default_stable()
    cfg["created_at"] = _now()
    _save_stable(cfg)
    return cfg


def list_versions() -> list:
    folder = _dir() / "versions"
    if not folder.exists():
        return []
    items = []
    for f in folder.glob("v*.json"):
        try:
            items.append(_read(f))
        except (OSError, ValueError):
            continue
    return sorted(items, key=lambda c: c.get("version", 0))


# ---- proposals -------------------------------------------------------------

def save_proposal(proposal: dict) -> None:
    _write(_dir() / "proposals" / f"{proposal['id']}.json", proposal)


def load_proposal(proposal_id: str) -> dict:
    if not proposal_id or not all(c.isalnum() or c in "-_" for c in proposal_id):
        raise VersionError("Invalid proposal id.")
    path = _dir() / "proposals" / f"{proposal_id}.json"
    if not path.exists():
        raise VersionError(f"Proposal not found: {proposal_id}")
    return _read(path)


def list_proposals() -> list:
    folder = _dir() / "proposals"
    if not folder.exists():
        return []
    items = []
    for f in folder.glob("*.json"):
        try:
            items.append(_read(f))
        except (OSError, ValueError):
            continue
    return sorted(items, key=lambda p: p.get("created_at", ""))


# ---- human-approved changes -------------------------------------------------

def promote(proposal_id: str, approver: str) -> dict:
    """Promote a *recommended* proposal to the new stable version. Human action only."""
    if not approver:
        raise VersionError("An approver is required.")
    proposal = load_proposal(proposal_id)
    if proposal.get("status") != "recommended":
        raise VersionError(
            f"Proposal status is '{proposal.get('status')}'; only 'recommended' can be promoted.")
    current = ensure_baseline()
    if proposal.get("base_version") != current["version"]:
        raise VersionError(
            f"Proposal was built on v{proposal.get('base_version')} but stable is "
            f"v{current['version']}. Run a new evaluation.")
    new = {
        "version": current["version"] + 1,
        "created_at": _now(),
        "note": f"promoted from {proposal_id}",
        "parent_version": current["version"],
        "promoted_from": proposal_id,
        "approved_by": approver,
        "world_additions": clean_additions(proposal.get("candidate_additions")),
    }
    _save_stable(new)
    proposal["status"] = "promoted"
    proposal["approved_by"] = approver
    proposal["promoted_at"] = new["created_at"]
    proposal["promoted_version"] = new["version"]
    save_proposal(proposal)
    return new


def rollback(version: int, approver: str) -> dict:
    """Restore an earlier version as a new, higher version number. Human action only."""
    if not approver:
        raise VersionError("An approver is required.")
    current = ensure_baseline()
    path = _dir() / "versions" / f"v{int(version)}.json"
    if not path.exists():
        raise VersionError(f"Version not found: v{version}")
    old = _read(path)
    new = {
        "version": current["version"] + 1,
        "created_at": _now(),
        "note": f"rollback to v{int(version)}",
        "parent_version": current["version"],
        "restored_from": int(version),
        "approved_by": approver,
        "world_additions": clean_additions(old.get("world_additions")),
    }
    _save_stable(new)
    return new
