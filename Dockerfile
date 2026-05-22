# Dockerfile for TisTru (Hugging Face Spaces / self-hosted Docker)
# Bundles FastAPI backend + Next.js frontend + local Ollama LLM server.
#
# Build:
#   docker build -t tistru .
# Run:
#   docker run -p 7860:7860 -e OLLAMA_MODEL=llama3.1 tistru
#
# For GPU support on HF Spaces, use a GPU-enabled Space template and
# ensure the Ollama binary can access CUDA libraries.

# Stage 1: Build the Next.js frontend
FROM node:20 AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
ENV NEXT_PUBLIC_API_URL=
RUN npm run build

# Stage 2: Python runtime with Ollama and FastAPI
FROM python:3.11-slim

# Install system dependencies and Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source
COPY backend/app ./backend/app

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/dist ./frontend/dist

# Copy startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Environment defaults for local LLM mode
ENV USE_LOCAL_LLM=true
ENV OLLAMA_BASE_URL=http://localhost:11434/v1
ENV OLLAMA_MODEL=llama3.1
ENV OLLAMA_HOST=0.0.0.0:11434

# HF Spaces default port
EXPOSE 7860

CMD ["/start.sh"]
