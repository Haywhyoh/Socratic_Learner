# Socratic Learner

Project-based and concept-based learning platform.

## Frontend

Next.js dashboard: course onboarding, milestone workspace, Monaco editor, coach chat, and hints. See [frontend/README.md](frontend/README.md).

```bash
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
```

Run the backend on port 8000 in another terminal.

## Backend

The first slice lives in [`backend/`](backend/). See [backend/README.md](backend/README.md) for setup, migrations, tests, and the CLI.

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# start Postgres (docker compose up -d db  OR  local createdb)
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload --port 8000
pytest
```
