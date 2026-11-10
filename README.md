# Inteligen — One Central Brain, Five Worlds

An experimental multi-perspective AI system that is developed and runs **entirely on GitHub** (no VPS, no server).

## Architecture (the project's fixed target)

| Component | Role | Where |
|---|---|---|
| 🧠 Central brain | Manages intelligence, decisions, coordinates the five worlds | `app/orchestrator.py`, `app/brain.py` |
| 🌐 Knowledge world | Learning and expanding knowledge | `app/worlds.py` |
| 🧩 Reasoning world | Strengthening logic and problem solving | `app/worlds.py` |
| 🔬 Science world | Hypotheses and experiments | `app/worlds.py` |
| 🎨 Creativity world | New ideas and solutions | `app/worlds.py` |
| 🧠 Learning world | Reviews performance, proposes improvement | `app/worlds.py` |
| 💾 Long-term memory | Stores and retrieves experiences (kinds: experience, experiment, decision, failure) | `app/memory.py`, `data/memory.sqlite3` |
| 🧪 Simulation lab | Isolated, repeatable tests of new methods | `app/simulation.py`, `evolution/benchmark.json` |
| 📈 Evaluation & evolution engine | Measures progress, proposes and compares versions, human-approved promotion and rollback | `app/evaluation.py`, `app/evolution.py`, `app/versions.py` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [ROADMAP.md](ROADMAP.md).

## Continuous learning: what it is and is not

The goal is **automatic, repeated learning cycles on GitHub Actions**, not an always-on AI. GitHub starts a short job every 2 hours (12 cycles/day, each roughly 10 minutes on CPU); the job restores the saved state, runs all five worlds on the next topic of a rotating curriculum, evaluates, saves the state and ends. The next cycle starts from that state.

What carries over between cycles: each world's own past outputs (hybrid keyword + character-similarity retrieval), coaching about the criteria that world's own recent outputs missed, per-world counters and score history, and lab results. **Model weights are never trained**; the five worlds share one small model and differ by prompt, memory and metrics.

Honest limits: GitHub may delay or skip scheduled runs; in public repositories it disables scheduled workflows after 60 days without repository activity (a commit or a manual run re-enables them); "learning" is measured by a keyword rubric on a small benchmark, so treat progress numbers as indicators, not proof.

Controls: pause with the repository variable `LEARNING_PAUSED=true` (Settings → Secrets and variables → Actions → Variables); resume by deleting it. Run once manually from Actions → GitHub Brain Cycle → Run workflow. Change the cadence by editing the `cron` line in `.github/workflows/github-brain.yml`.

## How it runs on GitHub

Three workflows, all on temporary GitHub-hosted runners (Ollama + `qwen3:1.7b`, model cached between runs):

1. **GitHub Brain Cycle** (manual + every 2 hours): tests → five worlds → central synthesis + assessment → rubric evaluation → saves memory, history and dashboard state to the **`state` branch** → deploys Pages.
2. **Evolution Engine** (manual + weekly): `evaluate` builds one candidate version and tests it against the stable version in the simulation lab; `promote` and `rollback` change the stable version. These are human actions: only people with write access can run the workflow, and the actor is recorded as approver.
3. **Deploy Pages** (on any change under `docs/`): publishes the dashboard without running the model.

Runtime state (memory, history, versions, proposals, `docs/state`) lives on the `state` branch, so workflows never push to a protected `main`. Each run restores it first (`scripts/state_sync.sh`). Code and config stay on `main`.

Dashboard: `https://iojh2021-oss.github.io/inteligen/` (Persian/English, RTL).

## First-time setup (works from a phone browser)

1. **Settings → Pages → Source: GitHub Actions.**
2. **Actions → GitHub Brain Cycle → Run workflow** two or three times (history is what the evolution engine learns from).
3. **Actions → Evolution Engine → Run workflow → action `evaluate`.** Read the proposal on the dashboard, including the sample outputs.
4. To accept: run Evolution Engine again with action `promote` and the proposal id. To undo: action `rollback` with a version number.

## The evolution loop (and its limits)

The engine looks at which rubric criteria the stable version keeps missing, adds the matching instruction from a **fixed library** (model output never becomes configuration), runs baseline vs candidate on a fixed benchmark, and recommends only if the paired score gain is clear and nothing regressed or became less reliable. A recommendation is never applied automatically.

Honest limits: the rubric counts keyword coverage of structural criteria, so a candidate can score higher just because the prompt asks for those words. "Recommended" means better rubric coverage on a small benchmark, not provably better answers. Read the samples before approving. Worlds still share one small model; they differ by prompt only.

## Important execution limits

This is serverless batch execution, not an always-on AI server. A runner exists only while a workflow runs. Scheduled workflows can be delayed and are disabled after 60 days without repository activity in public repositories. CPU inference is slow: one cycle takes roughly 10–20 minutes; one evaluation (2 benchmark questions × 2 versions) roughly an hour. Pages is static hosting and only displays published state.

## Public-data warning

This repository is public. Workflows commit questions, model outputs, SQLite memory, evolution history and lab samples to Git history. **Do not submit passwords, API keys, private personal information or confidential data.** Removing a later file does not erase earlier history.

## Status

Implemented: central brain with structural assessment; five worlds with failure isolation; versioned per-world guidance with promotion and rollback; memory kinds with provenance and forgetting; isolated simulation lab; paired-comparison evolution engine (proposal-only); bilingual dashboard; GitHub-only CI/CD.

Not yet implemented: semantic/vector memory, per-world datasets, quality evaluation beyond the keyword rubric, memory correction/approval workflow, larger benchmarks and repeated trials, separate models per world.
