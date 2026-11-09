"""Standalone smoke verification for the deterministic simulation laboratory."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import simulation


def main():
    with tempfile.TemporaryDirectory(prefix="inteligen-simulation-smoke-") as temp:
        os.environ["DATABASE_PATH"] = str(Path(temp) / "simulation.sqlite3")

        cases = [
            (
                "logistic_population",
                {
                    "initial_population": 10,
                    "growth_rate": 0.2,
                    "carrying_capacity": 100,
                    "steps": 12,
                },
            ),
            (
                "exponential_decay",
                {"initial_value": 100, "decay_rate": 0.1, "steps": 3},
            ),
        ]

        for scenario, parameters in cases:
            first = simulation.run_simulation(scenario, parameters)
            second = simulation.run_simulation(scenario, parameters)
            assert first["fingerprint"] == second["fingerprint"]
            assert first["result"] == second["result"]
            restored = simulation.get_run(first["run_id"])
            assert restored["fingerprint"] == first["fingerprint"]
            assert restored["deterministic"] is True
            print(
                f"PASS {scenario}: fingerprint={first['fingerprint']} "
                f"run_id={first['run_id']}"
            )

    print("SIMULATION_LAB_VERIFICATION=PASS")


if __name__ == "__main__":
    main()
