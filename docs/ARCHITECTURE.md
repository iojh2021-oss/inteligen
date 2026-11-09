# Architecture

## Request path
Browser -> Starlette -> central orchestrator -> knowledge / reasoning / science / creativity (independent) -> learning (reviews those four) -> central synthesis -> browser.

Each world retrieves its own relevant past work from SQLite memory (keyword overlap, with timestamps and request_id provenance). A failing world is recorded and reported but does not abort the request; only a total failure returns 503. Per-world success rate, latency and output size are stored and exposed at `/metrics`.

## Endpoints
- `POST /ask`: run the five worlds and central synthesis.
- `GET /memory`, `DELETE /memory/{id}`: inspect and forget stored memories.
- `GET /metrics`: per-world reliability and latency metrics.
- `POST /lab/compare`: compare current world prompts with an experiment-only candidate instruction on the same fixed five-world benchmark tasks.
- `GET /lab/experiments`: retrieve the most recent 20 experiment reports.
- `GET /health`, `GET /health/model`: service and model health.

## Simulation and evaluation lab
The lab runs each fixed benchmark through a baseline prompt and a candidate-instruction variant. Candidate instructions are appended only to the experiment request; they are not written into active prompts, source files, or deployment settings. Results are persisted in a dedicated SQLite table.

The current score is a deterministic structural heuristic: non-empty output, sufficient length, world-specific terms, reasoning signal, and uncertainty/limitations. This provides repeatable diagnostics, not semantic truth verification, scientific validation, or safety certification. A positive score does not automatically authorize promotion. The report always records `promotion: not_performed`.

## Model choice and trust
The initial adapter targets an OpenAI-compatible local endpoint. Suggested starter weights: Qwen/Qwen3-4B, published by the Qwen team. Its official model card declares Apache-2.0; the Qwen project's official repository says Qwen3 open-weight models use Apache 2.0. This verifies the upstream license statement, not the integrity of every third-party quantization or download mirror. Prefer the upstream publisher and verify checksums where supplied.

Official references:
- https://huggingface.co/Qwen/Qwen3-4B
- https://github.com/QwenLM/Qwen3

A 4B model is a practical starting point, not a claim that it is the strongest model. It may require quantization and suitable RAM/VRAM. Keep inference local when possible. For a hosted endpoint, review provider retention and privacy terms before sending prompts.

## Trust boundaries
- No shell, filesystem, browser, or external tool execution is exposed to model outputs.
- Model responses and candidate instructions are untrusted text; they cannot authorize host actions.
- The Learning World only suggests changes; it cannot edit source or deploy.
- The first version stores prompts and outputs in SQLite. GitHub-hosted cycles also persist the database in a public repository; do not submit secrets or private personal data.
- A human should review experiment reports and evaluation results before any production update.

## Known limitations
- Five worlds currently use one underlying model with different system prompts. They are not five independently trained models.
- Memory retrieval is keyword overlap over each world's last 200 entries, not semantic vector search. Memories are not yet reviewed/approved before sharing.
- Existing per-world runtime metrics measure reliability and speed, not answer quality. The new lab adds basic structural signals, not semantic judging.
- No fine-tuning or automatic architecture mutation is implemented.
- The experiment lab is sequential and uses a small fixed benchmark; it requires a reachable model endpoint.
- Model endpoint availability and quality must be tested in the target environment.

## Running on GitHub (Codespaces)
Open the repository in a Codespace (Code > Codespaces > Create). The dev container installs dependencies automatically. Then run `bash scripts/start_codespace.sh`, which starts Ollama with a small model and the server on port 8000. Codespaces is a development environment, not a hosting service: it stops after an idle period and uses a monthly free quota, so it is not an always-on server. The default model is small because a 2-core machine is slow; quality will be lower than the 4B model suggested for local hardware.
