# Long-term target architecture

The project's non-negotiable destination:

**One central brain + five independent learning worlds + long-term memory + a simulation laboratory + an evaluation and evolution engine.**

Constraint for now: no VPS or server. Everything is developed, tested and executed on GitHub (Actions, Pages).

## Safety boundary
No self-modifying production code, autonomous deployment, arbitrary shell execution, or unrestricted external tool access. Evolution only proposes and evaluates; a human promotes. Model output is untrusted input and never becomes configuration directly.

## Status by component
- **Central brain:** routing, dependency order, failure isolation, synthesis, structural assessment (`app/brain.py`). Done for the current scope.
- **Five worlds:** implemented as five prompts on one shared model, with versioned approved guidance. Independent datasets and learning state per world: not yet.
- **Long-term memory:** SQLite with provenance, timestamps, kinds, forgetting. Semantic search and correction/approval of shared memories: not yet.
- **Simulation lab:** isolated benchmark runs of prompt-level candidates (no memory, no tools, no synthesis). Scientific/world simulations beyond prompt candidates: not yet.
- **Evaluation & evolution:** keyword-rubric scoring, history, candidate generation from a fixed instruction library, paired comparison, human-approved promotion, rollback. Quality metrics that are not keyword-based, larger benchmarks and repeated trials: not yet.
- **Dashboard & CI/CD:** bilingual Pages dashboard, three workflows, model cache. Done.

## Continuous-learning acceptance checklist (honest status)
- [x] Scheduled workflow (every 2 hours) plus manual run, YAML tested, timeout 60 min, serialized by concurrency, one retry at most, pause switch.
- [x] State persists on the `state` branch (not on the temporary runner); validated before every push; verified memory backup and recovery.
- [x] All five worlds run every cycle; a failed world is recorded and does not stop the others; counters per world and overall are tested for consistency.
- [x] Previous-cycle experience is retrieved and used (tested across two runs, and simulated across three fresh clones).
- [x] Per-world metrics, history, memory retrieval and coaching.
- [x] Lab: fixed versioned benchmark, repeats, paired baseline/candidate comparison, benchmark/rubric change blocks promotion, per-world regression blocks recommendation.
- [x] Stable version only changes by human-run promote/rollback.
- [x] Dashboard shows real state and flags stale or missing data.
- [x] No VPS, server, or self-triggering workflow.
- [ ] Several real consecutive scheduled runs observed on GitHub with the real model.
- [ ] Measured improvement against baseline on the fixed benchmark over many cycles.
- [ ] Quality evaluation that does not depend on keywords (independent judge, source checking).
- [ ] Real experiments for the Science world (today it only proposes and predicts).

Status until the unchecked items are met: **in development**, not "complete independent continuous learning".

## Next phases
1. Run real cycles and evaluations; tune thresholds in `app/evolution.py` from observed noise.
2. Repeated trials per benchmark question and a larger, versioned benchmark.
3. A second, independent quality signal (for example pairwise comparison by a separate judge prompt) to reduce keyword gaming.
4. World-specific datasets and per-world state.
5. Semantic memory and a correction/approval flow.
6. Broader candidate types (parameters, retrieval settings) still behind human approval.

## Acceptance criteria
- A single request is routed to all five worlds and synthesized. ✔
- Each world has independent measurable metrics. ◐ (coverage and reliability; quality pending)
- Memory persists across runs with provenance. ✔
- Lab experiments are repeatable and isolated from production state. ✔
- Improvements are shown on a fixed benchmark and cannot regress reliability silently. ◐ (small benchmark)
- Failed candidates can be rejected and earlier versions restored. ✔
