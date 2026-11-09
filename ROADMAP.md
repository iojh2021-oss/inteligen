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
- Phase 1: implemented in code with an injectable model adapter, failure isolation, and end-to-end tests. The latest GitHub-hosted brain cycle completed all five worlds on Qwen3 1.7B.
- Phase 2: partial. Per-world retrieval and reliability metrics exist; independent datasets and quality metrics remain future work.
- Phase 3: started. Provenance, timestamps and forgetting exist. Experiment reports now persist separately in SQLite; memory correction and approval of shared memories remain future work.
- Phase 4: initial isolated prompt experiment runner implemented. It compares baseline and candidate instructions on fixed five-world tasks; a full stateful simulator remains future work.
- Phase 5: initial deterministic structural evaluator implemented with explainable checks. It is not a semantic correctness judge; stronger held-out datasets and calibrated quality metrics remain future work.
- Phase 6: candidate prompts are not automatically promoted and production code is never modified by the lab. Human-reviewed version approval and rollback remain future work.
