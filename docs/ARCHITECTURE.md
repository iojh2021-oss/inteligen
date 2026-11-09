# Architecture

## Components
- `app/orchestrator.py` runs the five worlds in dependency order and synthesizes. In **lab mode** it reads and writes no memory, records no metrics and skips synthesis.
- `app/brain.py` turns rubric coverage and world availability into a coverage level (low/medium/high), reasons, and whether human review is required. Structural only.
- `app/versions.py` stores the stable version, history of versions, and proposals as JSON under `evolution/`. Promotion needs a *recommended* proposal built on the current stable version; rollback restores an earlier version as a new version number.
- `app/simulation.py` runs a fixed benchmark (`evolution/benchmark.json`) for one set of per-world additions.
- `app/evolution.py` records history, derives one candidate from recurring missing criteria using a fixed instruction library, compares paired scores, writes proposals and exports `docs/state/*.json`.
- `scripts/run_github_cycle.py` and `scripts/run_evolution.py` are the GitHub Actions entry points.

## Request path
Browser -> Starlette -> central orchestrator -> knowledge / reasoning / science / creativity (independent) -> learning (reviews those four) -> central synthesis -> browser.

Each world retrieves its own relevant past work from SQLite memory (keyword overlap, with timestamps and request_id provenance). A failing world is recorded and reported but does not abort the request; only a total failure returns 503. Per-world success rate, latency and output size are stored and exposed at `/metrics`.

## Endpoints
`POST /ask`, `GET /memory`, `DELETE /memory/{id}` (forgetting), `GET /metrics`, `GET /health`, `GET /health/model` (probes the local model server).

## Model choice and trust
The initial adapter targets an OpenAI-compatible local endpoint. Suggested starter weights: Qwen/Qwen3-4B, published by the Qwen team. Its official model card declares Apache-2.0; the Qwen project's official repository says Qwen3 open-weight models use Apache 2.0. This verifies the upstream license statement, not the integrity of every third-party quantization or download mirror. Prefer the upstream publisher and verify checksums where supplied.

Official references:
- https://huggingface.co/Qwen/Qwen3-4B
- https://github.com/QwenLM/Qwen3

A 4B model is a practical starting point, not a claim that it is the strongest model. It may require quantization and suitable RAM/VRAM. Keep inference local when possible. For a hosted endpoint, review provider retention and privacy terms before sending prompts.

## Trust boundaries
- No shell, filesystem, browser, or external tool execution is exposed to model outputs.
- Model responses are untrusted text; do not treat them as instructions for the host.
- The Learning World only suggests changes; it cannot edit source or deploy.
- The first version stores prompts and outputs in local SQLite. Do not submit secrets or sensitive personal data.
- A human should review proposed changes and evaluation results before any production update.

## Known limitations
- Five worlds currently use one underlying model with different system prompts (plus approved per-world guidance). They are not five independently trained models.
- Memory retrieval is keyword overlap over each world's last 200 entries, not a semantic vector search. Memories are not yet reviewed/approved before sharing.
- Rubric scores measure keyword coverage of structural criteria, not answer quality or truth; a candidate can raise them just by asking for those words. The lab benchmark is small and each question runs once, so verdicts are noisy.
- No fine-tuning or automatic architecture mutation is implemented.
- Model endpoint availability and quality must be tested in the target environment.

## Running on GitHub (Codespaces)
Open the repository in a Codespace (Code > Codespaces > Create). The dev container installs dependencies automatically. Then run `bash scripts/start_codespace.sh`, which starts Ollama with a small model and the server on port 8000. Codespaces is a development environment, not a hosting service: it stops after an idle period and uses a monthly free quota, so it is not an always-on server. The default model is small because a 2-core machine is slow; quality will be lower than the 4B model suggested for local hardware.
