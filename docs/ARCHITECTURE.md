# Architecture

## Request path
Browser -> Starlette -> input safety gate -> central orchestrator -> knowledge / reasoning / science / creativity -> learning (reviews those four) -> output safety gate -> central synthesis -> final safety gate -> browser.

Each world retrieves its own relevant past work from SQLite memory. When the optional local multilingual embedding model is loaded, retrieval fuses BM25 lexical rank and dense cosine rank; otherwise it falls back to BM25. Records retain timestamps and request_id provenance. A failing world is recorded and reported but does not abort the request; only a total model failure returns 503. Per-world success rate, latency and output size are stored and exposed at /metrics.

## Safety boundary
- Guardrail v1 screens incoming prompts before any model call.
- Every world output is screened before it can be passed to another world or saved in memory.
- Central synthesis is screened again before it is returned or persisted.
- Flagged model output is replaced with a fixed safe response; the original flagged text is not written to memory or forwarded to another world.
- The filter uses explicit deterministic patterns for selected high-risk operational requests. It is a first-line control, not a complete classifier, independent safety audit, or guarantee. False positives and false negatives remain possible.
- Model prompts, retrieved memories and other-world outputs are untrusted data; they cannot override the safety boundary.
- No shell, filesystem, browser, or external tool execution is exposed to model outputs. The Learning World only suggests changes; it cannot edit source or deploy. Human review remains required.

## Endpoints
POST /ask, GET /memory, DELETE /memory/{id}, GET /metrics, GET /health, GET /health/model. The health response reports the guardrail version.

## Model choice and trust
The model adapter targets an OpenAI-compatible local endpoint. The GitHub brain-cycle workflow downloads Qwen3 weights with Ollama on a temporary GitHub-hosted runner. Five worlds currently share one underlying model with different system prompts; they are not five independently trained models.

Do not submit secrets or sensitive personal data: this repository is public. For hosted inference, review provider retention and privacy terms before sending prompts.

## Known limitations and next stages
- Five worlds are prompt-specialized roles on one base model, not separately trained agents.
- Semantic memory uses the local FastEmbed multilingual MiniLM model (384-dimensional vectors) with SQLite storage and reciprocal-rank fusion with BM25. The model is optional at runtime; unavailable downloads or inference safely fall back to BM25. GitHub Actions caches the model files and stores vectors in the SQLite memory cache. A full brain-cycle run must still verify model download, inference, and cross-run cache restore.
- The current evaluation rubric measures visible text coverage, not factual correctness, intelligence or learning.
- The deterministic safety filter covers only a small set of explicit patterns and is not comprehensive.
- Simulation experiments, outcome tracking, semantic retrieval, and measurable cross-run improvement still need implementation and validation.
- No fine-tuning or automatic architecture mutation is implemented.

## GitHub-only execution
The brain cycle runs on GitHub-hosted Actions with a local Ollama process on that temporary runner. No separate VPS or always-on inference server is required for the scheduled workflow. GitHub-hosted runners are temporary; durable memory requires a validated persistence mechanism.


## Memory and experiments
- World memory uses world-scoped hybrid retrieval: BM25 lexical ranking plus optional multilingual dense embeddings, combined by reciprocal-rank fusion. Each memory vector records a model version; embeddings from another model version are not mixed into the active index.
- Structured experience records retain hypothesis, prediction, expected metric, numeric prediction (when supplied), observation, explicit outcome status, evidence note and timestamps. Each world retrieves only its own experience history.
- Outcome status is explicitly provided by an evaluator; the model does not certify its own predictions. Numeric absolute error is reported only when predicted and observed values are comparable numeric values.

## Simulation laboratory
- The lab executes only two reviewed deterministic scenarios: discrete logistic population growth and exponential decay.
- Inputs are validated and bounded; user-supplied code is never executed.
- Results are persisted in SQLite and include a SHA-256 fingerprint of normalized inputs and deterministic outputs.
- A simulation result may be attached to a world's experience ledger only as inconclusive simulation-only evidence; it cannot automatically confirm or refute a real-world hypothesis.

## Additional API routes
- `GET /experiences?world=...` and `POST /experiences`
- `POST /experiences/{id}/resolve` and `GET /experiences/summary`
- `GET /simulations/scenarios`, `POST /simulations/run`, `GET /simulations/{id}`
- `POST /simulations/{id}/experience`

The existing root dashboard route is preserved. The health endpoint reports the guardrail version, retrieval mode, experience ledger and simulation-lab availability.


## Fixed cross-run evaluation
- Every GitHub brain cycle runs the same versioned, benign benchmark prompt for each of the five worlds (`five-world-fixed-v1`).
- Fixed-benchmark snapshots are stored separately from user-request evaluation snapshots in SQLite, preventing unlike prompts from being compared in the same history.
- The latest report is also written to `docs/state/benchmark.json`; per-world history and score deltas are included when prior snapshots are available.
- Rubric scores only measure textual criterion coverage. A higher score is not proof of factual correctness, reasoning quality, or learning. Human-reviewed held-out tasks are still needed.


## Multilingual semantic memory
- Embeddings are generated locally with FastEmbed and `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions, multilingual model).
- Embedding vectors for both ordinary memories and structured experience records are stored in SQLite by record ID, world, and model version. The five worlds never retrieve each other's memories.
- Hybrid ranking uses reciprocal-rank fusion rather than directly adding BM25 and cosine scores with different scales.
- Existing memories and experience records can be indexed incrementally with `POST /memory/semantic/backfill?limit=500`; status is exposed at `GET /memory/semantic`. Resolving an experience refreshes its vector so the observation and evidence note can affect later retrieval.
- The primary memory save succeeds even if embedding inference fails. Retrieval then uses BM25 as a fallback. Deleting a memory also deletes its stored vector.
- GitHub Actions restores/saves the FastEmbed model cache separately from SQLite memory. Unit tests use deterministic fake vectors and do not download the model.


## Evidence provenance and validation (next milestone)
- Every resolved experience can record an evidence source type, optional source reference, reviewer label, validation status, and SHA-256 fingerprint of the canonical evidence payload.
- A `confirmed` or `refuted` status requires manual-observation or external-reference evidence, an evidence note, and a reviewer label. External references also require a reference identifier.
- Simulation, model-generated, and unknown sources are restricted to `inconclusive`; simulation output is not promoted into real-world proof.
- The digest detects later payload changes only when compared with a trusted copy; it does not authenticate the source or reviewer. Reviewer labels are not identity verification.
- Existing experience rows remain readable and are reported as unverified when no provenance row exists.

## Per-world progress API
- `GET /progress` reports each world's own memory count, operational reliability/latency, experience outcomes, provenance counts, and latest fixed-benchmark score/trend.
- Progress is independent at the data and measurement level. The five worlds still share the same underlying model; this is not five separately trained models.
- Benchmark trend is a structural rubric signal, not proof of factual correctness or learning. At least two comparable benchmark snapshots are needed before a delta can be reported.
