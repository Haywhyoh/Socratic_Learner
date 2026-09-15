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
3. **Workspace** — milestone rail (locked until prior milestones complete), Monaco editor + file tree, run/tests output, coach panel with **Hint** button

## Backend CORS

The API allows `http://localhost:3000` by default (`CORS_ORIGINS` in backend `.env`). Add more origins comma-separated for other hosts.

## Stack

- Next.js App Router, TypeScript, Tailwind CSS v4
- `@monaco-editor/react` for in-browser editing
- JWT stored in `localStorage` (`socratic_access_token`)

## Not in this slice

- xterm.js terminal (output panel only for now)
- Concept-mode debate UI (placeholder message)
- Git UI in the browser
