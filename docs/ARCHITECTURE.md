# Architecture

## Request path
Browser -> FastAPI -> central orchestrator -> five specialist prompts -> shared SQLite memory -> central synthesis -> browser.

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
- Five worlds currently use one underlying model with different system prompts. They are not five independently trained models.
- Shared memory is a simple recent-history store, not a semantic vector database.
- No fine-tuning or automatic architecture mutation is implemented.
- Model endpoint availability and quality must be tested in the target environment.
