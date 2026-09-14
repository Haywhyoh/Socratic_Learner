# Socratic Learner — Backend

FastAPI + Postgres backend for project-based and concept-based learning. No frontend in this slice.

## Stack

- FastAPI / Pydantic v2 / SQLAlchemy 2.0
- PostgreSQL 16 (Docker Compose or local Homebrew Postgres)
- Alembic migrations
- JWT email/password auth
- Docker-based Python sandbox for learner code (never runs on the API process)
- pytest against a dedicated `socratic_test` database
- Typer CLI (`socratic`) for terminal use

## Setup

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### Database

**Option A — Docker Compose**

```bash
docker compose up -d db
```

Update `.env` if needed:

```
DATABASE_URL=postgresql+psycopg://socratic:socratic@localhost:5432/socratic
TEST_DATABASE_URL=postgresql+psycopg://socratic:socratic@localhost:5432/socratic_test
```

Create the test database once:

```bash
docker compose exec db createdb -U socratic socratic_test
```

**Option B — local Postgres (Homebrew)**

```bash
createdb socratic
createdb socratic_test
```

Default `.env.example` targets local trust auth as the current OS user.

### Migrate and seed

```bash
alembic upgrade head
python -m app.seed
```

### Python sandbox image

Learner code runs in ephemeral Docker containers. You need a Docker daemon.

**macOS (lightweight):** Colima

```bash
brew install docker colima
colima start
docker build -t socratic-sandbox-python:latest sandbox
```

**Or** install Docker Desktop, start it, then build the same image.

Sandbox settings (see `.env.example`):

```
SANDBOX_ENABLED=true
SANDBOX_IMAGE=socratic-sandbox-python:latest
SANDBOX_MEMORY_MB=512
SANDBOX_CPUS=1.0
SANDBOX_TIMEOUT_SEC=30
SANDBOX_PIDS_LIMIT=64
```

Workspaces live under `data/workspaces/{user_project_id}/` (gitignored). Containers use no network, CPU/memory/PID limits, and auto-cleanup. Allowlisted commands: `python`, `python3`, `pytest`.

This is a **local trust model**: the API host must be able to talk to the Docker daemon. Do not expose an unauthenticated Docker socket to learners. If the API cannot find Docker after Colima starts, set `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` and restart uvicorn.
### Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Open docs at http://localhost:8000/docs

## Tests

```bash
pytest
```

Tests use `TEST_DATABASE_URL` and recreate/truncate tables automatically. Sandbox unit tests use a fake runner (no Docker). Optional Docker smoke:

```bash
SOCRATIC_SANDBOX_DOCKER=1 pytest -m docker
```

## CLI

With the API running:

```bash
socratic auth register
socratic auth login
socratic courses
socratic options 1
socratic options 1 --parent-id 1
socratic enroll --course 1 --primary 1 --secondary 2 --mode project
socratic path
socratic brief
socratic sandbox init
socratic sandbox write main.py --content "print('hello')"
socratic sandbox run -- python main.py
socratic sandbox test
socratic milestone complete <user_milestone_id>
socratic concept show
socratic coach start
socratic roadmap
socratic cards
socratic hint
socratic start   # interactive walkthrough
```

Token is stored at `~/.socratic/token`.

## Learning flow

1. Register / login
2. Choose a course (Software Engineering or Business)
3. Choose primary option (Language / Domain) then secondary (Framework / Focus)
4. Choose `project` or `concept`
   - **project** — assigns the lowest-id matching active project and creates milestone progress rows
   - **concept** — assigns a seeded hard question when one exists for that path (`status=active`); otherwise creates a session with `question_text=null` and status `pending_generation` (AI later)
5. Complete milestones in order; restart from any milestone with
   `POST /api/v1/me/milestones/{id}/restart` (also resets later milestones)
6. Use the sandbox (`socratic sandbox init` / `write` / `run` / `test`) to implement and verify; test results are recorded on learner state (`tested=True`) for the coach
7. Start the project coach (`POST /api/v1/me/projects/{id}/coach/start` or
   `socratic coach start`) to assess prior knowledge, get a concept roadmap,
   and receive just-in-time concept cards for the current milestone
8. Chat with the senior-engineer mentor (`socratic coach message ...`);
   request progressive hints with `socratic hint` (effort-gated; real sandbox tests count as effort)

### Python seed content

- **FastAPI projects:** Task Tracker API, Notes API with Tags (each with 3 milestones)
- **Django project:** Library Catalog (3 milestones)
- **React project:** Learning Dashboard (3 milestones)
- **Business project:** Content Calendar Sprint (3 milestones)
- **Concept questions:** 3 for Python/FastAPI, 3 for Python/Django

Each project definition includes: objective, difficulty, prerequisites, expected outcome,
skills, concepts, milestones, constraints, tests, evaluation criteria, extension challenges,
and recommended resources. View via `GET /api/v1/projects/{id}` or `socratic brief`.
Each milestone also lists `concepts` used by the AI planner.

The project coach (LangGraph) personalizes teaching on top of that catalog: it does not
invent milestones. Concept cards stay short; the mentor asks you to implement rather than
pasting solutions. Hint levels unlock only after genuine effort.

### Anthropic (optional)

Default in code is `stub`. To use Claude Haiku/Sonnet, set in `.env`:

```
LLM_MODEL=anthropic:claude-haiku-4-5
ANTHROPIC_API_KEY=sk-ant-...
```

Install extras are already in `pyproject.toml` (`langchain-anthropic`). Restart uvicorn
after changing `.env`. Mentor chat uses the live model; cards and hint ladder stay
deterministic so policy (no solution dumps / no level-skipping) remains reliable.

Re-run seed safely anytime:

```bash
python -m app.seed
```

## Out of scope (this slice)

- Browser editor (Monaco / xterm)
- Git teaching workflows
- Gating milestone complete on green tests
- AI code review / project defense / completion levels
- Frontend
- OAuth / social login
- Admin CRUD UI
- Concept-mode tutor loop
