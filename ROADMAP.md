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
