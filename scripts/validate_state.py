"""Check that the restored state is consistent. Exit code 1 lists the problems."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app import state_guard  # noqa: E402

problems = state_guard.validate_state()
if problems:
    print("STATE PROBLEMS:")
    for item in problems:
        print(" -", item)
    sys.exit(1)
print("State is consistent.")
