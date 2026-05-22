#!/bin/bash
set -e

# Start Ollama in the background
ollama serve &
OLLAMA_PID=$!

# Wait until the Ollama API is responsive
echo "[start] Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
    sleep 1
done
echo "[start] Ollama is ready."

# Pull the configured model if it is not already present
if ! ollama list | grep -q "^${OLLAMA_MODEL}"; then
    echo "[start] Pulling model: ${OLLAMA_MODEL}"
    ollama pull "${OLLAMA_MODEL}"
else
    echo "[start] Model ${OLLAMA_MODEL} already present."
fi

# Start the FastAPI backend
echo "[start] Starting FastAPI on port 7860..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 7860
