#!/usr/bin/env bash
# Starts a local model (Ollama) and the Inteligen server inside a GitHub Codespace.
# A 2-core Codespace is slow: default to a small model. Override with MODEL_NAME=...
set -euo pipefail

export MODEL_NAME="${MODEL_NAME:-qwen3:1.7b}"
export MODEL_BASE_URL="${MODEL_BASE_URL:-http://127.0.0.1:11434/v1}"
export WORLD_CONCURRENCY="${WORLD_CONCURRENCY:-1}"
export REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-300}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Installing Ollama (official installer)..."
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! curl -fs http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama..."
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -fs http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

echo "Pulling model $MODEL_NAME (first time only)..."
ollama pull "$MODEL_NAME"

echo "Starting Inteligen on port 8000. Open the Ports tab and open the forwarded URL."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
