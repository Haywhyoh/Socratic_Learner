# Socratic Learner — Backend

FastAPI + Postgres backend for project-based and concept-based learning. No frontend and no AI generation in this slice.

## Stack

- FastAPI / Pydantic v2 / SQLAlchemy 2.0
- PostgreSQL 16 (Docker Compose or local Homebrew Postgres)
- Alembic migrations
- JWT email/password auth
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

### Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Open docs at http://localhost:8000/docs

## Tests

```bash
pytest
```

Tests use `TEST_DATABASE_URL` and recreate/truncate tables automatically.

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
socratic milestone complete <user_milestone_id>
socratic concept show
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

### Python seed content

- **FastAPI projects:** Task Tracker API, Notes API with Tags (each with 3 milestones)
- **Django project:** Library Catalog (3 milestones)
- **Concept questions:** 3 for Python/FastAPI, 3 for Python/Django

Re-run safely anytime:

```bash
python -m app.seed
```

## Out of scope (this slice)

- LLM question generation and argument scoring
- Frontend
- OAuth / social login
- Admin CRUD UI
