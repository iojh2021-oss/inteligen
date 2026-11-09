# Architecture

## Request path
Browser -> Starlette -> input safety gate -> central orchestrator -> knowledge / reasoning / science / creativity -> learning (reviews those four) -> output safety gate -> central synthesis -> final safety gate -> browser.

Each world retrieves its own relevant past work from SQLite memory (keyword overlap, with timestamps and request_id provenance). A failing world is recorded and reported but does not abort the request; only a total model failure returns 503. Per-world success rate, latency and output size are stored and exposed at /metrics.

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
- Memory retrieval is keyword overlap, not semantic vector search. Memory persistence between GitHub runs depends on the cache workflow being merged and validated by a subsequent full brain-cycle run.
- The current evaluation rubric measures visible text coverage, not factual correctness, intelligence or learning.
- The deterministic safety filter covers only a small set of explicit patterns and is not comprehensive.
- Simulation experiments, outcome tracking, semantic retrieval, and measurable cross-run improvement still need implementation and validation.
- No fine-tuning or automatic architecture mutation is implemented.

## GitHub-only execution
The brain cycle runs on GitHub-hosted Actions with a local Ollama process on that temporary runner. No separate VPS or always-on inference server is required for the scheduled workflow. GitHub-hosted runners are temporary; durable memory requires a validated persistence mechanism.
