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
| `ADMIN_PATH_SECRET` / `NEXT_PUBLIC_ADMIN_PATH_SECRET` | — | Obfuscated login path; admin UI lives at `/{secret}` |
| `ADMIN_EMAILS` | — | Comma-separated operator emails allowed for admin APIs |
| `TRUST_X_FORWARDED_FOR` | `false` | If `true`, anon quotas use the **rightmost** `X-Forwarded-For` hop (enable only behind a reverse proxy). If `false`, use the TCP peer IP only |
| `FACT_CHECK_ANON_LIMIT` | `1` | Free anonymous fact-checks per IP per UTC day |
| `FACT_CHECK_USER_DAILY_LIMIT` | `5` | Fact-checks per signed-in user per UTC day |
| `FACT_CHECK_RATE_LIMIT` / `FACT_CHECK_RATE_WINDOW_SECONDS` | `5` / `60` | Short burst limiter (defense in depth) |
| Firebase vars | — | See `backend/.env.example` and `frontend/.env.example` |

## End-user sign-in (Google)

Fact-check allows **one free anonymous** investigation per IP per day, then requires Google sign-in via Firebase Auth. Signed-in users get a configurable daily quota (default **5**).

1. Firebase Console → Authentication → Sign-in method → enable **Google**.
2. Ensure the web app’s authorized domains include your local and production hosts.
3. Set `NEXT_PUBLIC_FIREBASE_*` on the frontend and service-account credentials on the backend (Firestore stores usage counters).

Usage is tracked in Firestore (`usage_anon/*`, `usage_users/{uid}/days/{YYYY-MM-DD}`). If Firebase/Firestore is unavailable, fact-check fails closed with **503**.

## Admin

Admin access requires **both**:

1. Sign-in with **Email/Password** (Google accounts are end-users only).
2. That account’s email listed in backend `ADMIN_EMAILS` (comma-separated, case-insensitive).

| Provider | Role |
|---|---|
| Email/password + email in `ADMIN_EMAILS` | Admin (operators) |
| Email/password not in `ADMIN_EMAILS` | Denied |
| Google | Regular end-user (fact-check quota only) |

1. In Firebase Console → Authentication → Sign-in method: keep **Email/Password** enabled so operators can sign in (create operator users in the console).
2. Set `ADMIN_EMAILS` to those operator emails (e.g. `you@example.com`). Empty list denies all admin API access.
3. Enable **Google** for public end-users on the home page.
4. Set the same path secret in backend `ADMIN_PATH_SECRET` and frontend `NEXT_PUBLIC_ADMIN_PATH_SECRET`.
5. Open `http://localhost:3000/<secret>` (e.g. `change-me` → `/change-me`). Avoid reserved segments like `report`.
6. Sign in with an allowlisted **email/password** operator account; use Overview / Config / Traffic to manage runtime settings and view analytics.

Google accounts cannot use the admin UI, even if the email is listed in `ADMIN_EMAILS`.

## Running Locally

```bash
docker build -t tistru .
docker run -p 7860:7860 -e OLLAMA_MODEL=llama3.1 tistru
```

Then open [http://localhost:7860](http://localhost:7860).
