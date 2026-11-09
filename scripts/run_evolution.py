"""Evolution engine entry point for GitHub Actions.

  evaluate                      build + test one candidate in the simulation lab (needs the model)
  promote  --proposal ID        human-approved promotion of a recommended proposal
  rollback --version N          human-approved restore of an earlier version
  export                        refresh docs/state/*.json only
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPOSITORY_ROOT)
sys.path.insert(0, str(REPOSITORY_ROOT))

from app import evolution, model, versions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["evaluate", "promote", "rollback", "export"])
    parser.add_argument("--proposal", default="")
    parser.add_argument("--version", type=int, default=0)
    args = parser.parse_args()
    approver = os.environ.get("GITHUB_ACTOR", "")

    try:
        if args.action == "evaluate":
            if not asyncio.run(model.get_client().ping()):
                raise SystemExit("The local Ollama OpenAI-compatible endpoint is not reachable.")
            result = asyncio.run(evolution.evaluate_cycle())
            summary = result.get("proposal", {})
            print(json.dumps({
                "status": result["status"],
                "proposal": summary.get("id"),
                "verdict": (summary.get("comparison") or {}).get("verdict"),
                "message": result.get("message"),
            }, ensure_ascii=False))
        elif args.action == "promote":
            new = versions.promote(args.proposal.strip(), approver)
            print(json.dumps({"promoted_to": new["version"], "approved_by": approver}))
        elif args.action == "rollback":
            new = versions.rollback(args.version, approver)
            print(json.dumps({"restored_as": new["version"], "from": args.version,
                              "approved_by": approver}))
        versions.ensure_baseline()
        evolution.export_state()
    except versions.VersionError as exc:
        raise SystemExit(f"Refused: {exc}")


if __name__ == "__main__":
    main()
