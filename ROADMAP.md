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
2. Add world-specific state, datasets, metrics, and memory retrieval. **Current partial progress:** per-world memory is isolated and now uses deterministic BM25-style lexical ranking on the feature branch; world-specific datasets and capability-quality metrics remain outstanding.
3. Add durable long-term memory with provenance, timestamps, correction/forgetting support, and approved sharing.
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
- Phase 1: done in code (model adapter with injectable client, failure isolation, end-to-end tests). Needs a real run against the GitHub-hosted model cycle to confirm.
- Phase 2: partial. Per-world retrieval and reliability metrics exist; world-specific datasets and quality metrics do not yet.
- Phase 3: started. Provenance, timestamps and forgetting exist; correction and approval of shared memories do not.
- Phases 4-6: not started.
