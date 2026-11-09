# Inteligen — One Central Brain, Five Worlds

Inteligen is an experimental multi-perspective AI system coordinated by a central orchestrator.

## Target architecture

- **Central brain:** task routing, coordination, synthesis, uncertainty handling.
- **Knowledge world:** facts, concepts, evidence and source quality.
- **Reasoning world:** logic, assumptions and problem solving.
- **Science world:** testable hypotheses, predictions and safe experiments.
- **Creativity world:** alternative ideas and trade-offs.
- **Learning world:** reviews the other four worlds and proposes measurable improvements.
- **Long-term memory:** SQLite with per-world retrieval, timestamps and request provenance.
- **Simulation and evolution:** planned next phases; candidate changes must be evaluated and human-approved.

## Run on GitHub without a separate server

The `GitHub Brain Cycle` workflow runs the model locally on a temporary GitHub-hosted Actions runner:

1. It runs the regression tests.
2. It starts Ollama on the runner and downloads `qwen3:1.7b`.
3. The central orchestrator runs the five worlds and synthesis.
4. The workflow persists SQLite memory and dashboard snapshots in the repository.
5. The Pages dashboard reads the published JSON snapshots.

Start a cycle from **Actions → GitHub Brain Cycle → Run workflow**. You can provide a question or use the default review prompt. A daily scheduled review is also configured.

To publish the dashboard, open **Settings → Pages**, choose **Deploy from a branch**, select `main` and `/docs`. Then the site is available at:

`https://iojh2021-oss.github.io/inteligen/`

The first dashboard result appears after the first successful workflow run.

## Important execution limits

This is serverless batch execution, not an always-on AI server. A GitHub-hosted runner exists only for the duration of a workflow; it stops when the job ends. Scheduled workflows can be delayed, and GitHub automatically disables scheduled workflows in public repositories after 60 days without repository activity. Model download and CPU inference can be slow.

GitHub Pages is static hosting: it displays published state but does not execute the Python brain. The actual inference runs inside GitHub Actions.

## Public-data warning

This repository is public. The workflow commits the question, model outputs, and SQLite long-term memory to Git history so later runs can retrieve previous experience. **Do not submit passwords, API keys, private personal information, confidential data, or anything that should not be public.** Removing a later file does not erase earlier Git history.

## Current implementation status

- Five specialist roles and central synthesis: implemented.
- Per-world failure isolation and reliability/latency metrics: implemented.
- SQLite memory with per-world keyword retrieval and forgetting endpoint: implemented.
- Local OpenAI-compatible model adapter: implemented.
- GitHub-hosted Ollama inference workflow and persistent public state: added.
- Static GitHub Pages dashboard: added; Pages source must be enabled in repository settings.
- Semantic/vector memory, world-specific datasets, scientific simulation lab, quality benchmarks, candidate comparison and rollback: not yet implemented.
- The five worlds currently share one model with different system prompts. They are not five separately trained models.

See [ROADMAP.md](ROADMAP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
