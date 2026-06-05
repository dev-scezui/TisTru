# Dockerfile for TisTru (Hugging Face Spaces / self-hosted Docker)
# Bundles FastAPI backend + Next.js frontend + local Ollama LLM server.
#
# Build:
#   docker build -t tistru .
#
# Run locally:
#   docker run -p 7860:7860 -e OLLAMA_MODEL=llama3.1 tistru
#
# For GPU support on HF Spaces, use a GPU-enabled Space template.
# HF Spaces requires the app to listen on port 7860 and run as UID 1000.

# ─────────────────────────────────────────────
# Stage 1: Build the Next.js frontend
# ─────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app

# Install dependencies first (better layer caching)
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend ./

# NEXT_PUBLIC_API_URL is empty so the frontend calls the same origin (port 7860)
ENV NEXT_PUBLIC_API_URL=

# Produces .next/standalone + .next/static (requires output:'standalone' in next.config.js)
RUN npm run build

# ─────────────────────────────────────────────
# Stage 2: Python runtime + Ollama + FastAPI
# ─────────────────────────────────────────────
FROM python:3.11-slim

# ── System deps + Ollama ──────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        nodejs \
        npm \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user required by HF Spaces (UID must be 1000) ────────────
RUN useradd -m -u 1000 -s /bin/bash user \
    && mkdir -p /home/user/.ollama \
    && chown -R 1000:1000 /home/user

# ── App working directory ─────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ── Backend source ────────────────────────────
COPY backend/app ./backend/app

# ── Frontend build artifacts (Next.js standalone output) ─────────────────────
# Requires next.config.js to have: output: 'standalone'
COPY --from=frontend-builder /app/.next/standalone   ./frontend/
COPY --from=frontend-builder /app/.next/static       ./frontend/.next/static
COPY --from=frontend-builder /app/public             ./frontend/public

# ── Startup script ────────────────────────────
COPY start.sh /start.sh
RUN chmod +x /start.sh

# ── Fix ownership so UID 1000 can write everywhere ────────────────────────────
RUN chown -R 1000:1000 /app /start.sh

# ── Switch to non-root user ───────────────────
USER 1000

# ── Environment defaults ──────────────────────
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:/usr/local/bin:$PATH

# Ollama config
ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_MODELS=/home/user/.ollama/models
ENV OLLAMA_BASE_URL=http://localhost:11434/v1
ENV OLLAMA_MODEL=llama3.1

# App config
ENV USE_LOCAL_LLM=true
# HF Spaces only proxies port 7860
ENV PORT=7860

# ── Expose HF Spaces required port ───────────
EXPOSE 7860

CMD ["/start.sh"]