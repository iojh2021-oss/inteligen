"""Deterministic, bounded simulation laboratory.

Only reviewed built-in scenarios are executable. User-supplied Python/code is never
evaluated. Identical scenario inputs produce identical outputs and fingerprints.
"""
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config

SCENARIOS = {
    "logistic_population": {
        "description": "Discrete logistic growth with optional constant harvest.",
        "parameters": {
            "initial_population": {"type": "number", "minimum": 0.0, "maximum": 1000000000.0},
            "growth_rate": {"type": "number", "minimum": 0.0, "maximum": 2.0},
            "carrying_capacity": {"type": "number", "minimum": 0.001, "maximum": 1000000000.0},
            "steps": {"type": "integer", "minimum": 1, "maximum": 500},
            "harvest_per_step": {"type": "number", "minimum": 0.0, "maximum": 1000000000.0, "default": 0.0},
        },
        "assumptions": [
            "The environment and carrying capacity remain constant.",
            "Growth follows a discrete logistic equation.",
            "Harvest is a constant amount per step and population cannot become negative.",
            "This simplified model omits age structure, seasonality, migration, and random events.",
        ],
    },
    "exponential_decay": {
        "description": "Deterministic proportional decay of a quantity over fixed steps.",
        "parameters": {
            "initial_value": {"type": "number", "minimum": 0.0, "maximum": 1000000000000.0},
            "decay_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "steps": {"type": "integer", "minimum": 1, "maximum": 500},
        },
        "assumptions": [
            "The same proportional decay rate applies at every step.",
            "No external input or replenishment occurs.",
            "The model is deterministic and does not represent measurement noise.",
        ],
    },
}


def _database():
    path = Path(config.database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS simulation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scenario TEXT NOT NULL,
        parameters_json TEXT NOT NULL,
        result_json TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def _number(params, name, spec):
    value = params.get(name, spec.get("default"))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < spec["minimum"] or value > spec.get("maximum", float("inf")):
        raise ValueError(f"{name} is outside the allowed range")
    return value


def _integer(params, name, spec):
    value = params.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not spec["minimum"] <= value <= spec["maximum"]:
        raise ValueError(f"{name} is outside the allowed range")
    return value


def _normalize(scenario, parameters):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown simulation scenario")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be a JSON object")
    specs = SCENARIOS[scenario]["parameters"]
    unknown = set(parameters) - set(specs)
    if unknown:
        raise ValueError("Unknown parameters: " + ", ".join(sorted(unknown)))
    normalized = {}
    for name, spec in specs.items():
        if name not in parameters and "default" not in spec:
            raise ValueError(f"Missing parameter: {name}")
        if spec["type"] == "integer":
            normalized[name] = _integer(parameters, name, spec)
        else:
            normalized[name] = _number(parameters, name, spec)
    return normalized


def _execute(scenario, p):
    if scenario == "logistic_population":
        value = p["initial_population"]
        capacity = p["carrying_capacity"]
        series = [round(value, 8)]
        for _ in range(p["steps"]):
            value = max(
                0.0,
                value + p["growth_rate"] * value * (1.0 - value / capacity)
                - p["harvest_per_step"],
            )
            series.append(round(value, 8))
        return {
            "series": series,
            "final_value": series[-1],
            "net_change": round(series[-1] - series[0], 8),
            "peak_value": max(series),
        }
    if scenario == "exponential_decay":
        value = p["initial_value"]
        series = [round(value, 8)]
        for _ in range(p["steps"]):
            value *= 1.0 - p["decay_rate"]
            series.append(round(value, 8))
        return {
            "series": series,
            "final_value": series[-1],
            "remaining_fraction": (
                round(series[-1] / series[0], 8) if series[0] else 0.0
            ),
        }
    raise ValueError("Scenario is not implemented")


def run_simulation(scenario, parameters):
    normalized = _normalize(scenario, parameters)
    result = _execute(scenario, normalized)
    canonical = json.dumps(
        {"scenario": scenario, "parameters": normalized, "result": result},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    created_at = datetime.now(timezone.utc).isoformat()
    conn = _database()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO simulation_runs(
                    scenario,parameters_json,result_json,fingerprint,created_at
                ) VALUES(?,?,?,?,?)""",
                (
                    scenario,
                    json.dumps(normalized, sort_keys=True, allow_nan=False),
                    json.dumps(result, sort_keys=True, allow_nan=False),
                    fingerprint,
                    created_at,
                ),
            )
            run_id = int(cur.lastrowid)
    finally:
        conn.close()
    return {
        "run_id": run_id,
        "scenario": scenario,
        "parameters": normalized,
        "result": result,
        "fingerprint": fingerprint,
        "created_at": created_at,
        "assumptions": SCENARIOS[scenario]["assumptions"],
        "deterministic": True,
    }


def get_run(run_id):
    conn = _database()
    try:
        row = conn.execute(
            """SELECT id,scenario,parameters_json,result_json,fingerprint,created_at
               FROM simulation_runs WHERE id=?""",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    scenario = row[1]
    return {
        "run_id": row[0],
        "scenario": scenario,
        "parameters": json.loads(row[2]),
        "result": json.loads(row[3]),
        "fingerprint": row[4],
        "created_at": row[5],
        "assumptions": SCENARIOS[scenario]["assumptions"],
        "deterministic": True,
    }



def record_run_as_experience(
    run_id,
    world,
    hypothesis,
    prediction,
    expected_metric=None,
    predicted_value=None,
    confidence=None,
):
    """Attach a simulation observation to a world experience as inconclusive evidence.

    Simulation output is not external-world evidence, so this helper never marks
    a hypothesis confirmed or refuted automatically.
    """
    run = get_run(run_id)
    if run is None:
        raise ValueError("Simulation run not found")
    from app import memory

    experience_id = memory.record_experience(
        world=world,
        hypothesis=hypothesis,
        prediction=prediction,
        request_id=f"simulation:{run['fingerprint'][:16]}",
        expected_metric=expected_metric,
        predicted_value=predicted_value,
        confidence=confidence,
    )
    observed_value = run["result"].get("final_value")
    evidence = (
        f"Simulation-only evidence; scenario={run['scenario']}; "
        f"parameters={json.dumps(run['parameters'], sort_keys=True)}; "
        f"fingerprint={run['fingerprint']}"
    )
    return memory.resolve_experience(
        experience_id=experience_id,
        observed_outcome=(
            f"Simulation {run_id} produced {run['result']}"
        ),
        outcome_status="inconclusive",
        observed_value=observed_value,
        evidence_note=evidence,
    )
