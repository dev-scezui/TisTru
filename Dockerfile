# syntax=docker/dockerfile:1
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
#
# NEXT_PUBLIC_* is inlined into the Next.js client at build time:
#   - Space Variables  → Docker build-args (ARG below)
#   - Space Secrets    → BuildKit secret mounts (RUN --mount below)
# Prefer Variables for Firebase web config (it is public by design).

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

# HF Variables arrive as build-args; Secrets do not — see secret mounts on RUN.
ARG NEXT_PUBLIC_FIREBASE_API_KEY
ARG NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ARG NEXT_PUBLIC_FIREBASE_APP_ID
ARG NEXT_PUBLIC_ADMIN_PATH_SECRET
# Empty API URL → frontend calls the same origin (port 7860)
ENV NEXT_PUBLIC_API_URL= \
    NEXT_PUBLIC_FIREBASE_API_KEY=$NEXT_PUBLIC_FIREBASE_API_KEY \
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=$NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN \
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=$NEXT_PUBLIC_FIREBASE_PROJECT_ID \
    NEXT_PUBLIC_FIREBASE_APP_ID=$NEXT_PUBLIC_FIREBASE_APP_ID \
    NEXT_PUBLIC_ADMIN_PATH_SECRET=$NEXT_PUBLIC_ADMIN_PATH_SECRET

# Optional: bake NEXT_PUBLIC_* when ARG/secret mounts are present.
# HF/Docker also injects them at runtime via start.sh → public/runtime-config.js.
RUN --mount=type=secret,id=NEXT_PUBLIC_FIREBASE_API_KEY \
    --mount=type=secret,id=NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN \
    --mount=type=secret,id=NEXT_PUBLIC_FIREBASE_PROJECT_ID \
    --mount=type=secret,id=NEXT_PUBLIC_FIREBASE_APP_ID \
    --mount=type=secret,id=NEXT_PUBLIC_ADMIN_PATH_SECRET \
    set -eu; \
    for name in \
      NEXT_PUBLIC_FIREBASE_API_KEY \
      NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN \
      NEXT_PUBLIC_FIREBASE_PROJECT_ID \
      NEXT_PUBLIC_FIREBASE_APP_ID \
      NEXT_PUBLIC_ADMIN_PATH_SECRET; do \
      if [ -f "/run/secrets/$name" ]; then \
        export "$name=$(cat "/run/secrets/$name")"; \
      fi; \
    done; \
    if [ -n "${NEXT_PUBLIC_FIREBASE_API_KEY:-}" ]; then \
      echo "Frontend build: Firebase web config present."; \
    else \
      echo "Frontend build: Firebase web config empty (runtime-config.js will supply it)."; \
    fi; \
    npm run build

RUN test -d .next/standalone || \
    (echo "ERROR: .next/standalone not found. Add output:'standalone' to next.config.js" && exit 1)

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
        zstd \
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
ENV OLLAMA_MODEL=llama3.2:3b

# App config
ENV USE_LOCAL_LLM=true
# HF Spaces only proxies port 7860
ENV PORT=7860

# ── Expose HF Spaces required port ───────────
EXPOSE 7860

CMD ["/start.sh"]