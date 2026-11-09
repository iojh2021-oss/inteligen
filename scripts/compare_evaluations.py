"""Compare two saved Inteligen benchmark reports.

Example:
  python scripts/compare_evaluations.py baseline.json candidate.json
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evaluation import compare_reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, default=Path("comparison-report.json"))
    parser.add_argument("--max-regression", type=float, default=0.0)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    report = compare_reports(baseline, candidate, args.max_regression)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # A failed gate is a non-zero exit for CI; "review_candidate" is still
    # only a human-review recommendation, never an automatic promotion.
    if report["recommendation"] != "review_candidate":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
