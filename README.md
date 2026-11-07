# Five Worlds — One Evolving AI

A modular AI research project built around one central coordinator, five specialist worlds, and shared memory.

## The five worlds
1. Knowledge — organizes sourced facts and flags uncertainty.
2. Reasoning — decomposes problems and checks conclusions.
3. Science — proposes testable hypotheses and experiments.
4. Creativity — explores alternative ideas and combinations.
5. Learning — reviews outcomes and proposes measurable improvements.

The worlds are specialist roles, not five unrestricted independent agents. A central coordinator routes requests and consolidates their outputs.

## Ready-made model strategy
This project connects to an existing model through an OpenAI-compatible API; it does not train a foundation model from scratch. The default endpoint is a local Ollama-compatible server at http://localhost:11434/v1. Other compatible endpoints can be configured.

No model is bundled or silently trusted. Before use, check the selected model's publisher, license, model card, provenance, limitations, and data-handling terms. Never commit API keys.

## Quick start
1. Create a Python virtual environment.
2. Install requirements.txt.
3. Copy .env.example to .env and configure the model.
4. Start a compatible local model server.
5. Run: uvicorn app.main:app --host 127.0.0.1 --port 8000
6. Open http://127.0.0.1:8000/

## Safety and improvement boundary
The Learning world may recommend prompt/configuration changes and compare evaluations. It cannot rewrite source code, deploy code, execute arbitrary commands, or grant itself permissions. Changes require human review. External browsing and autonomous deployment are disabled in this first milestone.

## Milestone 1
- Five specialist worlds and central orchestration
- Shared SQLite memory with timestamps and world labels
- OpenAI-compatible model adapter
- Basic dashboard and health/config endpoints
- Baseline tests

This is a working foundation, not evidence of general intelligence or autonomous self-improvement. Quality depends on the selected model and evaluation data.
