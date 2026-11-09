import pytest

from app import evaluation, safety
from app.worlds import WORLDS


class FakeBenchmarkClient:
    def __init__(self):
        self.calls = []

    async def ping(self):
        return True

    async def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return (
            "Definition and concept; verified fact and assumption; uncertainty and "
            "evidence source limitation. First step and second step therefore; "
            "assumption, alternative and counterexample; conclusion. Hypothesis, "
            "prediction, experiment test, measurement and limitation. Two ideas and "
            "options, trade-off, combine and practical approach. Gap, weakness, "
            "measurable metric, evaluation benchmark test and improvement."
        )


@pytest.mark.asyncio
async def test_fixed_benchmark_runs_once_for_each_world_and_is_versioned():
    client = FakeBenchmarkClient()
    report = await evaluation.run_fixed_benchmark(client)

    assert len(client.calls) == 5
    assert set(report["worlds"]) == set(WORLDS)
    assert set(report["prompts"]) == set(WORLDS)
    assert report["benchmark_version"] == evaluation.FIXED_BENCHMARK_VERSION
    assert report["evaluated_worlds"] == 5
    assert all(item["status"] == "evaluated" for item in report["worlds"].values())
    assert all(safety.screen_text(item)["allowed"] for item in report["prompts"].values())


@pytest.mark.asyncio
async def test_fixed_benchmark_keeps_unavailable_world_explicit():
    class PartialClient(FakeBenchmarkClient):
        async def generate(self, system_prompt, user_prompt):
            if "Knowledge World" in system_prompt:
                from app.model import ModelUnavailable
                raise ModelUnavailable("test-only unavailable")
            return await super().generate(system_prompt, user_prompt)

    report = await evaluation.run_fixed_benchmark(PartialClient())
    assert report["worlds"]["knowledge"]["status"] == "unavailable"
    assert report["worlds"]["knowledge"]["score"] is None
    assert report["evaluated_worlds"] == 4


def test_fixed_benchmark_snapshots_are_separate_from_request_evaluations(db):
    report = evaluation.evaluate_worlds({
        name: "concept definition assumption fact uncertainty evidence "
              "step premise alternative conclusion hypothesis prediction "
              "experiment test limitation idea option tradeoff combine "
              "practical gap metric benchmark improve"
        for name in WORLDS
    })
    stored = evaluation.record_evaluation(report, run_type="fixed_benchmark")
    history = evaluation.evaluation_history(run_type="fixed_benchmark")

    assert stored["run_type"] == "fixed_benchmark"
    assert set(stored["snapshot_ids"]) == set(WORLDS)
    assert set(history["worlds"]) == set(WORLDS)
