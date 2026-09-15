# Socratic Learner — Frontend

Next.js dashboard for course selection, milestone-based project learning, Monaco editor, sandbox runs, coach chat, and progressive hints.

## Prerequisites

- Backend API running at `http://localhost:8000` (see [backend/README.md](../backend/README.md))
- Docker sandbox image built if you want Run/Tests to work

## Setup

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Flow

1. Register / sign in
2. **Onboard** — course → primary option → secondary option → project vs concept mode
3. **Workspace** — milestone rail, Monaco editor, **xterm sandbox terminal**, coach panel with **Hint**

### Terminal

The bottom panel is an xterm.js terminal wired to `POST /api/v1/me/projects/{id}/sandbox/run`. Learners can run allowlisted commands such as:

```bash
mkdir -p app
touch app/__init__.py app/main.py
ls -la
python -c "from fastapi import FastAPI"
uvicorn app.main:app --host 127.0.0.1 --port 8000
pytest -q
pip list
```

Use `help` inside the terminal for the full list. `cd` is handled client-side. There is **no network** in the sandbox (FastAPI/uvicorn/pytest are preinstalled in the image). Long-running servers are stopped after the sandbox timeout — use them as a smoke check, not a permanent process.

## Backend CORS

The API allows `http://localhost:3000` by default (`CORS_ORIGINS` in backend `.env`). Add more origins comma-separated for other hosts.

## Stack

- Next.js App Router, TypeScript, Tailwind CSS v4
- `@monaco-editor/react` for in-browser editing
- `@xterm/xterm` sandbox terminal (HTTP run API, not a live PTY)
- JWT stored in `localStorage` (`socratic_access_token`)

## Not in this slice

- Live interactive PTY / WebSocket streaming (commands are request/response)
- Concept-mode debate UI (placeholder message)
- Git UI in the browser
