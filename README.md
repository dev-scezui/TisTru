# TisTru

TisTru is an AI-assisted fact-checking website. It accepts a public URL and optionally an uploaded image, extracts the artifact context, summarizes the claims, searches independent sources, scores the evidence, and generates a verdict report.

## Stack

- Backend: FastAPI, HTTPX, BeautifulSoup, OpenAI SDK, Tavily search integration
- Frontend: Next.js (App Router), React, TypeScript, Lucide icons

## Current pipeline

1. Fetch the submitted URL.
2. Extract title, caption-like metadata, description, readable text, images, videos, and uploaded image key details.
3. Summarize the context and extract checkable claims.
4. Search for evidence with Tavily when `TAVILY_API_KEY` is set.
5. Generate a score card and final verdict.
6. Use an OpenAI-compatible AI endpoint or a local Ollama LLM for stronger summarization and rationale.
7. Store the report and redirect to a unique, shareable results page (`/report/{id}`).

Without AI or search settings, the app still runs in demo mode with heuristic summarization and placeholder evidence guidance.

## Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000`.

Create `frontend/.env.local` from `frontend/.env.example`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Environment variables

Create `backend/.env` from `backend/.env.example`.

```envc
USE_LOCAL_LLM=false
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY=
FRONTEND_ORIGIN=http://localhost:3000
REQUEST_TIMEOUT_SECONDS=20
FIREBASE_CREDENTIALS_PATH=
FIREBASE_SERVICE_ACCOUNT_JSON=
```

### AI provider toggle

- `USE_LOCAL_LLM=false` (default): Uses the OpenAI-compatible API path (`OPENAI_API_KEY` / `OPENAI_BASE_URL`).
- `USE_LOCAL_LLM=true`: Routes LLM calls to the bundled Ollama server via `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.

For local OpenAI-compatible models **without** Ollama, set `OPENAI_BASE_URL` and `OPENAI_MODEL`. Many local servers do not require a real key, so `OPENAI_API_KEY` can be blank.

For persistent report storage you have three options:

1. **Service account JSON as an env var** (easiest for deploy platforms):
   Paste the entire contents of your Firebase service account JSON into `FIREBASE_SERVICE_ACCOUNT_JSON` as a single-line string.

2. **Service account JSON file**:
   Set `FIREBASE_CREDENTIALS_PATH` to the path of your Firebase service account JSON file.

3. **Auto-discovery (Google Cloud only)**:
   Leave both blank. On Cloud Run, App Engine, or GCE, the Firebase Admin SDK will auto-discover credentials.

If Firebase is not configured, reports are stored in-memory and will be lost on restart.

Examples:

**Local Ollama (toggle on)**

```env
USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1
```

**External OpenAI-compatible API (toggle off)**

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

## Docker deployment (Hugging Face Spaces)

A root `Dockerfile` is included that bundles the **Next.js frontend**, **FastAPI backend**, and **Ollama server** into one image.

```bash
docker build -t tistru .
docker run -p 7860:7860 -e OLLAMA_MODEL=llama3.1 tistru
```

- The container builds the frontend as a static export, starts `ollama serve`, pulls the configured model if missing, then launches FastAPI on port `7860`.
- FastAPI serves the frontend at `/` and proxies API calls to `/api/*` internally.
- You can override the model at runtime with `-e OLLAMA_MODEL=<model>`.
- For GPU Spaces, ensure the Space runtime uses a GPU template so Ollama can access CUDA.

## Important limitations

- Some social platforms block scraping or require official APIs.
- Video understanding is currently metadata extraction only, not frame/audio analysis.
- Verdicts should be treated as assisted analysis, not absolute truth.
- Production use should add rate limiting, job queues, auth, audit logs, and source allow/deny policy.
