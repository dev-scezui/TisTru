---
title: TisTru
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# TisTru

A locally-hosted LLM application powered by Ollama + FastAPI + Next.js, running entirely inside a single Docker container on Hugging Face Spaces.

## Architecture

```
Browser
  │
  ▼ :7860
FastAPI (backend/app/main.py)
  ├── /api/*  → LLM routes (Ollama on localhost:11434)
  └── /*      → Reverse-proxied to Next.js (localhost:3000)
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1` | Model to pull and use |
| `USE_LOCAL_LLM` | `true` | Set to `false` to use an external OpenAI-compatible API |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API base URL |
| `PORT` | `7860` | App port (do not change on HF Spaces) |

## Running Locally

```bash
docker build -t tistru .
docker run -p 7860:7860 -e OLLAMA_MODEL=llama3.1 tistru
```

Then open [http://localhost:7860](http://localhost:7860).