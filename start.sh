#!/bin/bash
# start.sh — TisTru startup script for Hugging Face Spaces
# Starts: Ollama (LLM server) → pulls model → FastAPI backend → Next.js frontend
# Everything funnels through a single port (7860) via FastAPI static file serving
# or a reverse proxy pattern.

set -euo pipefail

PORT="${PORT:-7860}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434/v1}"
USE_LOCAL_LLM="${USE_LOCAL_LLM:-true}"

echo "========================================"
echo "  TisTru — Starting services"
echo "  Port     : $PORT"
echo "  LLM mode : $USE_LOCAL_LLM"
echo "  Model    : $OLLAMA_MODEL"
echo "========================================"

# ── 1. Start Ollama in background (only in local LLM mode) ───────────────────
if [ "$USE_LOCAL_LLM" = "true" ]; then
    echo "[1/4] Starting Ollama daemon..."
    ollama serve &
    OLLAMA_PID=$!

    # Wait until Ollama API is reachable (up to 30 s)
    echo "[1/4] Waiting for Ollama to be ready..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:11434/ > /dev/null 2>&1; then
            echo "[1/4] Ollama is ready."
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "[ERROR] Ollama did not start within 30 seconds. Exiting."
            exit 1
        fi
        sleep 1
    done

    # ── 2. Pull the model if not already cached ──────────────────────────────
    echo "[2/4] Pulling model '$OLLAMA_MODEL' (skipped if already cached)..."
    ollama pull "$OLLAMA_MODEL"
    echo "[2/4] Model ready."
else
    echo "[1/4] USE_LOCAL_LLM=false — skipping Ollama startup."
    echo "[2/4] Skipping model pull."
fi

# ── 3. Start Next.js frontend in background ───────────────────────────────────
# The standalone build runs its own Node server on port 3000 internally.
# FastAPI (or a reverse proxy in start.sh) forwards /  requests to it.
NEXT_PORT=3000
echo "[3/4] Starting Next.js frontend on internal port $NEXT_PORT..."
cd /app/frontend
HOSTNAME=0.0.0.0 PORT=$NEXT_PORT node server.js &
NEXT_PID=$!
cd /app

# Wait for Next.js to be ready
for i in $(seq 1 20); do
    if curl -sf http://localhost:$NEXT_PORT/ > /dev/null 2>&1; then
        echo "[3/4] Next.js is ready."
        break
    fi
    if [ "$i" -eq 20 ]; then
        echo "[WARN] Next.js did not respond within 20 seconds — continuing anyway."
    fi
    sleep 1
done

# ── 4. Start FastAPI backend (foreground, keeps container alive) ──────────────
# FastAPI listens on 0.0.0.0:7860 and serves the API.
# Static/frontend requests are reverse-proxied to Next.js on port 3000
# via the proxy logic in backend/app/main.py (or handled by a middleware).
echo "[4/4] Starting FastAPI backend on port $PORT..."
exec uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info