# Long-term target architecture

The project's non-negotiable destination is:

**One central brain + five independent learning worlds + long-term memory + a simulation laboratory + an evaluation and evolution engine.**

## Core architecture
- **Central brain:** coordinates work, routes tasks, resolves disagreements, and integrates results.
- **Five independent learning worlds:** Knowledge, Reasoning, Science, Creativity, and Learning. Each world must eventually have its own evaluation data, learning state, and progress metrics while sharing approved memories.
- **Long-term memory:** durable, searchable, source-aware memory for facts, experiences, hypotheses, experiments, failures, and outcomes.
- **Simulation laboratory:** isolated sandbox for repeatable experiments and safe testing of proposed changes.
- **Evaluation and evolution engine:** independent benchmarks, regression checks, comparison against prior versions, and controlled promotion or rollback of improvements.

## Development phases
1. Stabilize the current five-role prototype and prove the model adapter works end-to-end.
2. Add world-specific state, datasets, metrics, and memory retrieval.
3. Add durable long-term memory with provenance, timestamps, and correction/forgetting support.
4. Build a sandboxed simulation and experiment runner.
5. Add a reproducible evaluation harness and baseline comparisons.
6. Add a proposal-only evolution loop: generate candidate changes, test in isolation, compare on held-out tests, and require human approval before promotion.

## Acceptance criteria
- A single request can be routed to all five worlds and synthesized by the central brain.
- Each world has independent measurable capability metrics.
- Memory persists across restarts and can be searched with provenance.
- Simulation experiments are repeatable and isolated from the host.
- Improvements are demonstrated on held-out evaluations and do not regress safety or reliability.
- Failed candidates can be rejected and previous stable versions restored.

## Safety boundary
No self-modifying production code, autonomous deployment, arbitrary shell execution, or unrestricted external tool access. The evolution engine proposes and evaluates changes; a human approves promotion. Model output is untrusted input.

## Status
- Phase 1: done in code (model adapter with injectable client, failure isolation, end-to-end tests). Needs a real run against your local model server to confirm.
- Phase 2: partial. Per-world retrieval and reliability metrics exist; per-world datasets and quality metrics do not yet.
- Phase 3: started. Provenance, timestamps and forgetting exist; correction and approval of shared memories do not.
- Phases 4-6: not started.


## Next implementation milestone: evidence provenance and world progress
- Add a provenance ledger to each resolved experience: source type, reference, reviewer label, evidence digest, and validation status.
- Require documented review metadata before a result can be labelled confirmed/refuted. Simulation-only and model-generated evidence remain inconclusive.
- Expose `GET /progress` with separate per-world memory, experience, reliability, evidence, and fixed-benchmark trend summaries.
- Keep the distinction explicit: isolated state and evaluation do not yet mean independently trained models or verified learning.
- Acceptance: provenance validation tests, API tests, five-world isolation tests, full pytest, compileall, then a GitHub Actions run. Keep the changes on a review branch until green.
